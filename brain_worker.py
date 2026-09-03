import os
import io
import time
import json
import logging
import re
import requests
import traceback
import urllib.request
import urllib.parse

from supabase import create_client, Client
from applywizz_brain import ApplyWizzBrain

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s')

# No hardcoded fallback: a leaked service_role key bypasses RLS entirely, so
# this must only ever come from the deploy environment. Fail loudly if unset
# rather than silently running with a stale/leaked default.
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

def get_db_client():
    return create_client(SUPABASE_URL, SUPABASE_KEY)

# ─────────────────────────────────────────────
# RESUME TEXT EXTRACTOR
# ─────────────────────────────────────────────

def extract_resume_text(resume_url):
    if not resume_url or not PdfReader:
        return ""
    try:
        req = urllib.request.Request(resume_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=20) as response:
            pdf_bytes = response.read()
        reader = PdfReader(io.BytesIO(pdf_bytes))
        text = ""
        for page in reader.pages:
            text += (page.extract_text() or "") + "\n"
        logging.info(f"  Extracted {len(text)} chars from resume")
        return text
    except Exception as e:
        logging.warning(f"  Could not extract resume: {e}")
        return ""

# ─────────────────────────────────────────────
# ZIP CODE LOOKUP (OpenStreetMap — free, no key)
# ─────────────────────────────────────────────

def lookup_zip_code(street, city, state):
    try:
        import urllib.parse
        query = urllib.parse.urlencode({
            'street': street or '', 'city': city or '',
            'state': state or '', 'country': 'US',
            'format': 'json', 'addressdetails': '1', 'limit': '1'
        })
        url = f"https://nominatim.openstreetmap.org/search?{query}"
        req = urllib.request.Request(url, headers={'User-Agent': 'ApplyWizz/1.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            results = json.loads(resp.read().decode())
        if results:
            postcode = results[0].get('address', {}).get('postcode', '')
            if postcode:
                logging.info(f"  📮 Found zip code: {postcode}")
                return postcode
    except Exception as e:
        logging.warning(f"  Could not look up zip code: {e}")
    return ''

# ─────────────────────────────────────────────
# JOB SCHEMA CACHE — scan each job ONCE ever
# ─────────────────────────────────────────────

def normalize_job_url(url):
    """
    Resolve grnh.se shortlinks and produce a stable cache key.
    We keep gh_jid (job ID for custom domains) but strip gh_src (tracking noise).
    """
    import re
    if 'grnh.se' in url:
        try:
            resp = requests.get(url, allow_redirects=True, timeout=10, headers={'User-Agent': 'Mozilla/5.0'})
            url = resp.url
        except Exception:
            pass
    # Strip only tracking params (gh_src), keep gh_jid which identifies the job
    url = re.sub(r'[?&]gh_src=[^&]*', '', url)
    url = re.sub(r'\?$', '', url)  # clean trailing ?
    return url.rstrip('/')


def parse_greenhouse_ids(url):
    for pattern in [
        # (?:\w+\.)? allows a region subdomain — e.g. boards.eu.greenhouse.io,
        # job-boards.eu.greenhouse.io — which real jobs use (confirmed: NICE,
        # ClinChoice, Datapao, and 9 others in a single 387-job batch) and
        # which the bare "boards.greenhouse.io" match used to miss entirely,
        # failing the job before it ever got a question schema.
        r"boards\.(?:\w+\.)?greenhouse\.io/([^/]+)/jobs/(\d+)",
        r"job-boards\.(?:\w+\.)?greenhouse\.io/([^/]+)/jobs/(\d+)",
        r"for=([^&]+).*token=(\d+)",
    ]:
        m = re.search(pattern, url)
        if m:
            return m.group(1), m.group(2)

    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    job_id = (qs.get("gh_jid") or qs.get("gh_src") or [""])[0]
    if job_id and job_id.isdigit():
        host_parts = parsed.netloc.split(".")
        board = host_parts[-2] if len(host_parts) >= 2 else host_parts[0]
        return board, job_id
    return None, job_id


def discover_board_token(canonical, job_id):
    resp = requests.get(canonical, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    html = resp.text
    for pattern in [
        r'"board_token"\s*:\s*"([^"]+)"',
        r"'board_token'\s*:\s*'([^']+)'",
        r'boards-api\.greenhouse\.io/v1/boards/([^/"?]+)/jobs/',
        r'job-boards\.(?:\w+\.)?greenhouse\.io/([^/"?]+)/jobs/',
    ]:
        m = re.search(pattern, html)
        if m:
            return m.group(1)
    raise ValueError(f"Cannot discover Greenhouse board token for job {job_id}: {canonical}")


def fetch_greenhouse_job_data(canonical):
    board_token, job_id = parse_greenhouse_ids(canonical)
    if not board_token or not job_id:
        raise ValueError(f"Cannot parse board_token/job_id from: {canonical}")

    api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=true"
    resp = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    if resp.status_code == 404:
        board_token = discover_board_token(canonical, job_id)
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=true"
        resp = requests.get(api_url, headers={"User-Agent": "Mozilla/5.0"}, timeout=20)
    resp.raise_for_status()
    return board_token, job_id, resp.json()


def get_or_cache_job_schema(supabase, raw_url):
    """
    Fetch the Greenhouse job schema ONCE per unique job URL.
    All candidates sharing the same job reuse the cached schema — zero extra API calls.
    """
    import re
    canonical = normalize_job_url(raw_url)

    cached = supabase.table("job_schemas").select("job_data").eq("canonical_url", canonical).execute()
    if cached.data:
        logging.info(f"  📦 JOB SCHEMA CACHED — zero Greenhouse API calls needed")
        return cached.data[0]["job_data"]

    logging.info(f"  🔍 New job — scanning Greenhouse API once: {canonical}")
    board_token, job_id, job_data = fetch_greenhouse_job_data(canonical)

    q_count = len(job_data.get("questions") or [])
    logging.info(f"  ✅ Scanned: '{job_data.get('title','')}' — {q_count} questions. Caching forever.")

    supabase.table("job_schemas").upsert({
        "canonical_url":  canonical,
        "raw_url":        raw_url,
        "board_token":    board_token,
        "job_id":         str(job_id),
        "job_title":      job_data.get("title", ""),
        "question_count": q_count,
        "job_data":       job_data,
    }).execute()

    return job_data

# ─────────────────────────────────────────────
# CANDIDATE PROFILE CACHE
# ─────────────────────────────────────────────

def get_or_cache_candidate(supabase, applywizz_id):
    resp = supabase.table("candidate_profiles").select("*").eq("applywizz_id", applywizz_id).execute()
    if resp.data:
        logging.info(f"CACHED profile for {applywizz_id} — no API call needed")
        return {"profile_json": resp.data[0]["profile_json"], "resume_text": resp.data[0].get("resume_text", "")}

    logging.info(f"First time: fetching {applywizz_id} from CRM API...")
    api_resp = requests.get(f"https://www.apply-wizz.me/api/get-client-details?applywizz_id={applywizz_id}", timeout=15)
    if api_resp.status_code != 200:
        raise Exception(f"CRM API returned {api_resp.status_code} for {applywizz_id}")

    profile_json = api_resp.json()
    if not isinstance(profile_json, dict) or not profile_json.get("client"):
        # CRM returned 200 with a null/empty/malformed body — a real, distinct
        # failure from an HTTP error, but process_pending_jobs' except block
        # still needs something to catch instead of crashing on .get() below.
        raise Exception(f"CRM API returned no usable profile for {applywizz_id} (got: {profile_json!r})")

    resume_url = profile_json.get("additional_information", {}).get("resume_url", "")
    resume_text  = extract_resume_text(resume_url)

    supabase.table("candidate_profiles").upsert({
        "applywizz_id": applywizz_id,
        "profile_json": profile_json,
        "resume_text":  resume_text
    }).execute()
    logging.info(f"Saved {applywizz_id} to candidate_profiles!")
    return {"profile_json": profile_json, "resume_text": resume_text}

# ─────────────────────────────────────────────
# CANDIDATE DICT BUILDER
# ─────────────────────────────────────────────

def build_candidate_dict(applywizz_id, profile_json):
    client   = profile_json.get("client", {})
    add_info = profile_json.get("additional_information", {})

    full_name   = client.get("full_name", "Unknown Name")
    name_parts  = full_name.split(" ", 1)
    first_name  = name_parts[0]
    last_name   = name_parts[1] if len(name_parts) > 1 else ""

    full_address  = add_info.get("full_address", "")
    address_parts = [p.strip() for p in full_address.split(",")] if full_address else []
    street = address_parts[0] if address_parts else ""
    zip_code = ""
    for part in address_parts:
        if part.strip().isdigit() and len(part.strip()) == 5:
            zip_code = part.strip()
    state = add_info.get("state_of_residence", "")
    city  = ""
    for i, part in enumerate(address_parts):
        if state and state.lower() in part.lower() and i > 0:
            city = address_parts[i - 1].strip()
            break
    if not city and len(address_parts) >= 3:
        city = address_parts[-4].strip() if len(address_parts) >= 4 else address_parts[1].strip()
    if not zip_code and (city or state):
        zip_code = lookup_zip_code(street, city, state)

    return {
        "applywizz_id":          applywizz_id,
        "first_name":            first_name,
        "last_name":             last_name,
        "email":                 client.get("personal_email", ""),
        "phone":                 client.get("callable_phone", ""),
        "full_address":          full_address,
        "street_address":        street,
        "city":                  city,
        "state":                 state,
        "zip_code":              zip_code,
        "country":               "United States",
        "linkedin":              add_info.get("linked_in_url", ""),
        "website":               add_info.get("github_url", ""),
        "resume_url":            add_info.get("resume_url", ""),
        "cover_letter_url":      add_info.get("cover_letter_path", "") or "",
        "visa_status":           client.get("visa_type", "Citizen"),
        "require_sponsorship":   add_info.get("require_future_sponsorship", False),
        "sponsorship":           client.get("sponsorship", False),
        "salary_expectation":    client.get("salary_range", "Open to discussion"),
        "willing_to_relocate":   add_info.get("willing_to_relocate", True),
        "can_work_onsite":       add_info.get("can_work_3_days_in_office", True),
        "highest_education":     add_info.get("highest_education", ""),
        "university":            add_info.get("university_name", ""),
        "gpa":                   add_info.get("cumulative_gpa", ""),
        "graduation_year":       add_info.get("graduation_year", ""),
        "main_subject":          add_info.get("main_subject", ""),
        "experience_years":      add_info.get("experience", ""),
        "role":                  add_info.get("role", ""),
        "gender":                add_info.get("gender", ""),
        "race":                  add_info.get("race_ethnicity", ""),
        "race_ethnicity":        add_info.get("race_ethnicity", ""),
        "is_hispanic_latino":    add_info.get("is_hispanic_latino", ""),
        "veteran":               add_info.get("veteran_status", ""),
        "veteran_status":        add_info.get("veteran_status", ""),
        "disability":            add_info.get("disability_status", ""),
        "disability_status":     add_info.get("disability_status", ""),
        "sexual_orientation":    add_info.get("sexual_orientation", None),
        "transgender_status":    add_info.get("transgender_status", None),
        "eeoc_unanswered_policy": add_info.get("eeoc_unanswered_policy", "ASK"),
        "is_over_18":            add_info.get("is_over_18", True),
        "eligible_to_work_in_us": add_info.get("eligible_to_work_in_us", True),
        "willing_background_check": add_info.get("willing_background_check", True),
        "willing_drug_screen":   add_info.get("willing_drug_screen", True),
        "convicted_of_felony":   add_info.get("convicted_of_felony", False),
        "pending_investigation": add_info.get("pending_investigation", False),
        "discharged_for_policy_violation": add_info.get("discharged_for_policy_violation", False),
        "can_provide_legal_docs": add_info.get("can_provide_legal_docs", True),
        "date_of_birth":         add_info.get("date_of_birth", ""),
        "has_relatives_in_company": add_info.get("has_relatives_in_company"),
        "_full_client":          client,
        "_full_additional":      add_info,
    }

# ─────────────────────────────────────────────
# MAIN WORKER LOOP
# ─────────────────────────────────────────────

def process_pending_jobs():
    supabase = get_db_client()
    logging.info("BRAIN WORKER: Checking for PENDING jobs...")

    response = supabase.table("job_queue").select("*").in_("status", ["PENDING", "PENDING_NEW"]).limit(50).execute()
    jobs = response.data

    if not jobs:
        logging.info("No PENDING jobs found.")
        return

    logging.info(f"Found {len(jobs)} PENDING jobs.")

    # In-memory schema cache for this batch run.
    # Even within one batch, same URL → reused instantly.
    batch_schema_cache = {}

    for job in jobs:
        job_id       = job['id']
        url          = job['url']
        client_name  = job['client_name']
        applywizz_id = job.get('applywizz_id')

        logging.info(f"\n{'='*60}\nJob [{job_id}] | {client_name} | {applywizz_id}\nURL: {url}")

        answer_map = None
        try:
            if not applywizz_id:
                raise Exception("Row is missing applywizz_id")

            # ── Step 1: Job schema — fetch ONCE, cache forever ──
            canonical = normalize_job_url(url)
            if canonical not in batch_schema_cache:
                batch_schema_cache[canonical] = get_or_cache_job_schema(supabase, url)
                logging.info(f"  📋 {len(batch_schema_cache[canonical].get('questions',[]))} questions loaded")
            else:
                logging.info(f"  ⚡ In-batch reuse — zero Supabase/API calls for schema")
            job_data = batch_schema_cache[canonical]

            # ── Step 2: Candidate profile ──
            cached       = get_or_cache_candidate(supabase, applywizz_id)
            profile_json = cached["profile_json"]
            resume_text  = cached["resume_text"]
            candidate    = build_candidate_dict(applywizz_id, profile_json)

            # ── Step 3: Memory Bank ──
            memory_resp = supabase.table("ai_memory_bank").select("question_label, answer").eq(
                "applywizz_id", applywizz_id
            ).execute()
            memory_bank = {}
            if memory_resp.data:
                for row in memory_resp.data:
                    val = row.get("answer", "")
                    if val and val not in ("AI_PLACEHOLDER", "AI_ANSWER_PENDING_API_KEY", "+", "None"):
                        memory_bank[row['question_label']] = val
                if memory_bank:
                    logging.info(f"  Loaded {len(memory_bank)} clean answers from Memory Bank")

            # ── Step 4: Brain Answer Engine ──
            brain = ApplyWizzBrain(
                job_url=url,
                candidate_profile=candidate,
                memory_bank=memory_bank,
                resume_text=resume_text,
            )
            brain._prefetched_job_data = job_data   # inject cached schema — skip Greenhouse API
            answer_map = brain.process()

            # Count how many need human attention
            needs_attention = sum(1 for a in answer_map.get("answer_map", []) if a.get("status") == "NEEDS_ATTENTION")
            logging.info(f"Job [{job_id}] done. {needs_attention} fields need human attention. → NEEDS_REVIEW")

            supabase.table("job_queue").update({
                "status": "NEEDS_REVIEW",
                "error_message": None,
                "application_data": answer_map
            }).eq("id", job_id).execute()

        except Exception as e:
            logging.error(f"Error on Job [{job_id}]: {e}\n{traceback.format_exc()}")
            supabase.table("job_queue").update({
                "status": "ERROR",
                "error_message": str(e),
                "application_data": answer_map
            }).eq("id", job_id).execute()

        time.sleep(1)


if __name__ == "__main__":
    while True:
        process_pending_jobs()
        logging.info("Sleeping 30s before next check...")
        time.sleep(30)
