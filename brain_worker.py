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
from datetime import datetime, timezone, timedelta

from supabase import create_client, Client
from applywizz_brain import ApplyWizzBrain, OPENROUTER_API_KEY, OPENROUTER_MODEL

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

try:
    import openai
except ImportError:
    openai = None

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


def _get_with_backoff(url, timeout=20, max_retries=3):
    """
    GET with retry on 429 (rate-limited) — mirrors the same backoff pattern
    applywizz_brain.py's AI router already uses (1s, 3s, 9s). Neither
    fetch_greenhouse_job_data nor discover_board_token had this before —
    at real volume, a burst of unique jobs hitting boards-api.greenhouse.io
    with zero retry could turn a transient rate-limit into a wave of ERROR
    jobs that a moment's wait would have avoided.
    """
    for attempt in range(max_retries):
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=timeout)
        if resp.status_code != 429:
            return resp
        if attempt < max_retries - 1:
            wait = 3 ** attempt
            logging.warning(f"  ⏳ Greenhouse rate-limited (429) — retrying in {wait}s...")
            time.sleep(wait)
    return resp  # last response, still 429 — caller's raise_for_status() surfaces it


def discover_board_token(canonical, job_id):
    resp = _get_with_backoff(canonical, timeout=20)
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
    resp = _get_with_backoff(api_url, timeout=20)
    if resp.status_code == 404:
        board_token = discover_board_token(canonical, job_id)
        api_url = f"https://boards-api.greenhouse.io/v1/boards/{board_token}/jobs/{job_id}?questions=true"
        resp = _get_with_backoff(api_url, timeout=20)
    resp.raise_for_status()
    return board_token, job_id, resp.json()


# Weight per question, approximating ORD §13's complexity table using only
# the fields this codebase has ever actually parsed from Greenhouse's public
# API (label, required, values/answer_options) — Greenhouse's raw response
# was never fully inspected here, so a genuine per-control TYPE (dropdown vs.
# checkbox vs. date picker vs. conditional field) can't be told apart the way
# the ORD describes. This approximates by option count instead: free text (no
# options) is cheapest, a short option list is a simple choice, a long one is
# closer to a real multi-select. Tier D ("unsupported form") is deliberately
# NOT assigned here — nothing in this codebase currently detects a genuinely
# unsupported control at parse time, so claiming to would be a guess, not a
# measurement.
def _question_weight(q):
    options = q.get("values") or q.get("answer_options") or []
    n = len(options)
    if n == 0:
        return 1
    if n <= 3:
        return 2
    return 3


def calculate_complexity(job_data):
    """
    Returns (complexity_score, automation_tier) for a job's parsed schema.
    Tier thresholds are intentionally simple and adjustable — ORD §14 says
    as much ("exact thresholds should remain configurable"). Counts both
    regular and demographic questions, since demographic questions add real
    review burden even though they're auto-resolved.
    """
    questions = job_data.get("questions") or []
    demo = (job_data.get("demographic_questions") or {}).get("questions") or []
    all_q = list(questions) + list(demo)

    score = sum(_question_weight(q) for q in all_q)
    q_count = len(all_q)

    if q_count <= 10 and score <= 20:
        tier = "A"
    elif q_count <= 20 and score <= 45:
        tier = "B"
    else:
        tier = "C"

    return score, tier


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
    complexity_score, automation_tier = calculate_complexity(job_data)
    logging.info(f"  ✅ Scanned: '{job_data.get('title','')}' — {q_count} questions, complexity {complexity_score} (Tier {automation_tier}). Caching forever.")

    supabase.table("job_schemas").upsert({
        "canonical_url":     canonical,
        "raw_url":           raw_url,
        "board_token":       board_token,
        "job_id":            str(job_id),
        "job_title":         job_data.get("title", ""),
        "question_count":    q_count,
        "complexity_score":  complexity_score,
        "automation_tier":   automation_tier,
        "job_data":          job_data,
    }).execute()

    return job_data

# ─────────────────────────────────────────────
# CANDIDATE PROFILE CACHE
# ─────────────────────────────────────────────

# Was a permanent, never-expiring cache — a candidate's info fetched once
# would never be re-checked again no matter how stale it got (new resume,
# updated phone number, anything). Now refreshed from the CRM once per day
# per candidate, and only for candidates who actually have a job to process
# that day — never a blanket daily refresh for everyone, which would hit
# the CRM for inactive candidates for no reason.
CANDIDATE_PROFILE_REFRESH_HOURS = 24


def _is_profile_fresh(updated_at_str) -> bool:
    if not updated_at_str:
        return False
    try:
        updated_at = datetime.fromisoformat(str(updated_at_str).replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - updated_at) < timedelta(hours=CANDIDATE_PROFILE_REFRESH_HOURS)
    except Exception:
        return False


def get_or_cache_candidate(supabase, applywizz_id):
    resp = supabase.table("candidate_profiles").select("*").eq("applywizz_id", applywizz_id).execute()
    if resp.data:
        row = resp.data[0]
        if _is_profile_fresh(row.get("updated_at")):
            logging.info(f"CACHED profile for {applywizz_id} — no API call needed (refreshed within {CANDIDATE_PROFILE_REFRESH_HOURS}h)")
            return {
                "profile_json": row["profile_json"],
                "resume_text": row.get("resume_text", ""),
                "parsed_address": row.get("parsed_address"),
            }
        logging.info(f"Cached profile for {applywizz_id} is older than {CANDIDATE_PROFILE_REFRESH_HOURS}h — refreshing from CRM...")
    else:
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

    full_address = profile_json.get("additional_information", {}).get("full_address", "")
    parsed_address = parse_address_with_ai(full_address)

    supabase.table("candidate_profiles").upsert({
        "applywizz_id": applywizz_id,
        "profile_json": profile_json,
        "resume_text":  resume_text,
        "parsed_address": parsed_address,
        # Upsert leaves columns you don't pass untouched on an UPDATE — the
        # table's DEFAULT now() only fires on INSERT, so this has to be set
        # explicitly every time or the freshness check above would never see
        # a newer timestamp on a refresh and would refetch on every single
        # job for that candidate forever.
        "updated_at":   datetime.now(timezone.utc).isoformat(),
    }).execute()
    logging.info(f"Saved {applywizz_id} to candidate_profiles!")
    return {"profile_json": profile_json, "resume_text": resume_text, "parsed_address": parsed_address}

# ─────────────────────────────────────────────
# ADDRESS PARSER (AI) — replaces the old comma-splitting heuristic
# ─────────────────────────────────────────────

_address_ai_client = None


def _get_address_ai_client():
    global _address_ai_client
    if _address_ai_client is None and openai:
        _address_ai_client = openai.OpenAI(base_url="https://openrouter.ai/api/v1", api_key=OPENROUTER_API_KEY)
    return _address_ai_client


def parse_address_with_ai(full_address: str):
    """
    Ask the AI to split a raw CRM address string into street/city/state/zip.

    Replaces the old heuristic in build_candidate_dict, which split on
    commas and guessed which piece was the city based on where the state
    name happened to appear (with an index-guessing fallback when that
    didn't work) — silently wrong for any address format it didn't expect.
    Called once per candidate, alongside the CRM fetch/refresh in
    get_or_cache_candidate — never per-job, so a candidate applying to 50
    jobs still only gets their address parsed once every 24h.

    Returns None (never a guess) if there's no address, the AI call fails,
    or the response isn't valid JSON with the expected shape — the caller
    must fall back to something safe rather than trust a None as real data.
    """
    if not full_address or not full_address.strip():
        return None
    client = _get_address_ai_client()
    if not client:
        return None

    prompt = (
        "Extract the street address, city, US state (2-letter abbreviation), "
        "and ZIP/postal code from the address below. Reply with ONLY a JSON "
        'object and nothing else: {"street": "...", "city": "...", '
        '"state": "...", "zip_code": "..."}. Use an empty string for any part '
        "you cannot determine from the text. Never invent information that "
        "isn't present in the address.\n\n"
        f"Address: {full_address}"
    )
    try:
        response = client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.choices[0].message.content.strip()
        raw = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL).strip()
        raw = re.sub(r"^```(?:json)?|```$", "", raw, flags=re.MULTILINE).strip()
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return None
        return {
            "street":   str(parsed.get("street") or ""),
            "city":     str(parsed.get("city") or ""),
            "state":    str(parsed.get("state") or ""),
            "zip_code": str(parsed.get("zip_code") or ""),
        }
    except Exception as e:
        logging.warning(f"  Address AI parse failed for '{full_address[:60]}...' (falling back): {e}")
        return None

# ─────────────────────────────────────────────
# CANDIDATE DICT BUILDER
# ─────────────────────────────────────────────

def build_candidate_dict(applywizz_id, profile_json, parsed_address=None):
    client   = profile_json.get("client", {})
    add_info = profile_json.get("additional_information", {})

    full_name   = client.get("full_name", "Unknown Name")
    name_parts  = full_name.split(" ", 1)
    first_name  = name_parts[0]
    last_name   = name_parts[1] if len(name_parts) > 1 else ""

    full_address = add_info.get("full_address", "")
    state = add_info.get("state_of_residence", "")

    if parsed_address and parsed_address.get("city"):
        # Real AI-parsed address (cached once per candidate) — reliable
        # regardless of how the CRM's free-text address is formatted.
        street   = parsed_address.get("street", "")
        city     = parsed_address.get("city", "")
        zip_code = parsed_address.get("zip_code", "")
        state    = state or parsed_address.get("state", "")
    else:
        # Fallback only: no AI-parsed address cached yet (or parsing failed)
        # for this candidate — same comma-splitting heuristic as before,
        # kept only so a candidate is never left with a fully blank address
        # while waiting for the next daily refresh to pick up parsed_address.
        address_parts = [p.strip() for p in full_address.split(",")] if full_address else []
        street = address_parts[0] if address_parts else ""
        zip_code = ""
        for part in address_parts:
            if part.strip().isdigit() and len(part.strip()) == 5:
                zip_code = part.strip()
        city = ""
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
        # Must be the monitored applywizz.ai mailbox, never the candidate's
        # personal email — muscle_worker.py's OTP and confirmation checks
        # poll Zoho for whatever email actually got submitted on the form,
        # and Zoho only has access to applywizz.ai inboxes. Submitting a
        # personal email here means every future OTP/confirmation check for
        # this job silently times out — no error, just a wait that can
        # never succeed.
        "email":                 client.get("company_email", ""),
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

        # Claim atomically before doing any real work. The plain SELECT above
        # has no lock — if brain_worker ever runs as more than one replica
        # (Railway shows 1 today, but muscle_worker.py is explicitly built
        # for multiple), two replicas could both fetch this same row and
        # both fully process it: duplicate CRM calls, duplicate Greenhouse
        # fetches, duplicate real AI spend, for the same job. The WHERE
        # status=<original status> guard is enforced by Postgres regardless
        # of which replica's request arrives first; checking claim.data
        # (not just assuming success) is what actually closes the race —
        # a blind update-without-checking-the-result is the same gap that
        # made muscle_worker.py's own single-worker fallback path unsafe.
        claim = supabase.table("job_queue").update({"status": "PROCESSING"}).eq(
            "id", job_id
        ).eq("status", job["status"]).execute()
        if not claim.data:
            logging.info(f"  ⏭️ Job [{job_id}] already claimed by another worker — skipping.")
            continue

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
            cached         = get_or_cache_candidate(supabase, applywizz_id)
            profile_json   = cached["profile_json"]
            resume_text    = cached["resume_text"]
            parsed_address = cached.get("parsed_address")
            candidate      = build_candidate_dict(applywizz_id, profile_json, parsed_address)

            # Hard business rule: never apply for a candidate with no
            # monitored applywizz.ai mailbox on file. Without one, Zoho has
            # nothing to read, so OTP/confirmation can never be verified —
            # applying anyway would submit real applications no one can ever
            # confirm went through. Fails into the same ERROR path/status
            # every other Step 2/3 failure already uses, so this needs no
            # new status and shows up in the dashboard exactly like any
            # other failed job.
            if not candidate["email"]:
                raise Exception(
                    f"No monitored applywizz.ai email on file for {applywizz_id} — "
                    "refusing to apply since OTP/confirmation could never be verified."
                )

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
            error_update = {"status": "ERROR", "error_message": str(e)}
            # answer_map is only set once Step 4 actually runs — a failure in
            # an earlier step (schema fetch, CRM fetch) must not overwrite any
            # application_data this row already had (e.g. from a prior attempt
            # someone manually reset from ERROR back to PENDING for a retry).
            if answer_map is not None:
                error_update["application_data"] = answer_map
            supabase.table("job_queue").update(error_update).eq("id", job_id).execute()

        time.sleep(1)


if __name__ == "__main__":
    while True:
        process_pending_jobs()
        logging.info("Sleeping 30s before next check...")
        time.sleep(30)
