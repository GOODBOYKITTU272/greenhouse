"""
ApplyWizz MUSCLE WORKER — Phase 4: Database-Driven Execution Engine
=========================================================
Reads APPROVED jobs from Supabase job_queue and executes
the form fill with local Playwright on Railway.

FIXES APPLIED:
1. DataImpulse Residential Proxy properly integrated
2. Label-based smart form-filling (field_type no longer needed)
3. Resume filename extracted from S3 URL (not hardcoded)
4. Real success detection + OTP handler via Zoho Mail Reader API
5. Dynamic target clients loaded from Supabase candidate_profiles
"""

import json
import logging
import os
import re
import time
from datetime import datetime, timezone
import requests
from typing import Optional
from playwright.sync_api import sync_playwright
from supabase import create_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("MUSCLE")

# No hardcoded fallback: a leaked service_role key bypasses RLS entirely, so
# this must only ever come from the deploy environment. Fail loudly if unset
# rather than silently running with a stale/leaked default.
SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
WORKER_ID = os.environ.get("RAILWAY_REPLICA_ID") or os.environ.get("HOSTNAME") or "local-muscle-worker"
SCREENSHOT_DIR = os.environ.get("SCREENSHOT_DIR", "screenshots")

# ── DataImpulse Residential Proxy Config ──
# No hardcoded fallback credentials here either — same reasoning as the
# Supabase key above. Must come from the environment.
if os.environ.get("PROXY_CONFIG"):
    PROXY_CONFIG = json.loads(os.environ["PROXY_CONFIG"])
else:
    PROXY_CONFIG = {
        "server": os.environ["PROXY_SERVER"],
        "username": os.environ["PROXY_USERNAME"],
        "password": os.environ["PROXY_PASSWORD"],
    }

# ── Zoho Mail Reader API ──
ZOHO_READER_BASE = os.environ.get("ZOHO_BASE_URL", "https://zoho-mail-reader.onrender.com").rstrip("/")

# ── Connect to Supabase ──
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def block_resources(route):
    """Cost Optimization: Block images, CSS, fonts to save DataImpulse bandwidth."""
    if route.request.resource_type in ['image', 'stylesheet', 'font', 'media']:
        route.abort()
    else:
        route.continue_()


def download_resume(url):
    log.info(f"Downloading resume from S3: {url}")
    try:
        resp = requests.get(url, timeout=60)
        resp.raise_for_status()
        if len(resp.content) < 5_000:
            raise ValueError(f"Resume is too small: {len(resp.content)} bytes")
        log.info(f"Resume downloaded: {len(resp.content)} bytes")
        return resp.content
    except Exception as e:
        log.error(f"Resume download failed: {e}")
        return None


def get_otp_from_zoho(candidate_email: str, company_name: str, after_ts_ms: int) -> Optional[str]:
    """
    FIX 4: Call Zoho Mail Reader API to retrieve Greenhouse OTP security code.
    Retries up to 4 times with 15s intervals (email may take up to 60s to arrive).
    """
    url = f"{ZOHO_READER_BASE}/api/zoho/greenhouse-security-code"
    params = {
        "email": candidate_email,
        "company": company_name,
        "receivedAfter": after_ts_ms
    }
    deadline = time.time() + 300
    attempt = 0
    while time.time() < deadline:
        attempt += 1
        try:
            log.info(f"🔑 Checking Zoho for OTP (attempt {attempt})...")
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                code = data.get("code") or data.get("otp") or data.get("security_code")
                if code:
                    log.info("🔑 OTP received.")  # never log the actual code
                    return str(code)
            log.info("   OTP not yet available, waiting 5s...")
            time.sleep(5)
        except Exception as e:
            log.warning(f"   Zoho OTP API error: {e}")
            time.sleep(5)
    return None


def confirmation_email_received(candidate_email: str, company_name: str, after_ts_ms: int) -> bool:
    """
    Polls the Zoho inbox for a confirmation email. Requires BOTH a known
    confirmation phrase AND the candidate's own email address to appear in
    the response — matching on phrase alone let one candidate's real
    confirmation email verify a completely different candidate's job.
    """
    url = f"{ZOHO_READER_BASE}/api/zoho/ui/inbox"
    deadline = time.time() + 600
    params = {"email": candidate_email, "company": company_name, "receivedAfter": after_ts_ms}
    while time.time() < deadline:
        try:
            resp = requests.get(url, params=params, timeout=15)
            if resp.status_code == 200:
                text = resp.text.lower()
                has_confirmation_phrase = any(
                    s in text for s in ["thank you for applying", "application received", "received your application"]
                )
                is_for_this_candidate = candidate_email.lower() in text
                if has_confirmation_phrase and is_for_this_candidate:
                    return True
                elif has_confirmation_phrase and not is_for_this_candidate:
                    log.warning(
                        f"   ⚠️ Confirmation phrase found but not addressed to {candidate_email}; "
                        "ignoring to avoid cross-candidate false positive."
                    )
        except Exception as e:
            log.warning(f"   Zoho confirmation check error: {e}")
        time.sleep(8)
    return False


def get_company_name_from_url(job_url: str) -> str:
    """Extract company name from Greenhouse URL for OTP lookup."""
    match = re.search(r'greenhouse\.io/([^/]+)/jobs', job_url)
    if match:
        return match.group(1).replace('-', ' ').replace('_', ' ').title()
    return "Company"


def select_us_country_code(page):
    try:
        control = page.locator(".iti__selected-flag, input#country, input[aria-label*='country' i]").first
        if control.count() == 0:
            return
        control.click(force=True)
        page.keyboard.type("United States")
        page.keyboard.press("Enter")
        page.wait_for_timeout(500)
    except Exception as e:
        log.warning(f"Country selector skipped: {e}")


def _option_plausibly_matches(option_text: str, answer: str) -> bool:
    """Loose but non-blind check used before force-clicking an autocomplete
    suggestion that didn't exactly contain the answer text: requires at
    least one shared meaningful word, so we don't silently select the wrong
    city or school just because it happened to be first in the dropdown."""
    opt_words = {w for w in re.split(r'\W+', option_text.lower()) if len(w) >= 3}
    ans_words = {w for w in re.split(r'\W+', answer.lower()) if len(w) >= 3}
    return bool(opt_words & ans_words)


def smart_fill_field(page, label: str, answer: str, filled: list, failed: list):
    if not answer or not answer.strip():
        return

    label_clean = label.replace('*', '').strip()

    # Pre-process Answer Strings to match exactly
    if answer == "Straight":
        answer = "Heterosexual"
    elif answer == "I am not a protected veteran":
        answer = "I do not fall into one of the above categories of “protected veteran”"
    elif answer == "No, I do not have a disability":
        answer = "No, I don’t have a disability"

    try:
        selectors = page.evaluate(f"""(labelText) => {{
            let cleanTarget = labelText.replace('*', '').trim().toLowerCase().split('?')[0].trim();
            // Greenhouse renders yes/no and EEOC-style questions as a
            // <fieldset><legend>question</legend> group, not a <label> —
            // the label-only search below would never see these at all.
            let questionEls = [...document.querySelectorAll('label'), ...document.querySelectorAll('legend')];
            let found = [];
            for(let l of questionEls) {{
                let cleanLabel = l.innerText.replace('*', '').trim().toLowerCase().split('?')[0].trim();
                if(cleanLabel === cleanTarget || cleanLabel.includes(cleanTarget) || cleanTarget.includes(cleanLabel)) {{
                    let container = l.tagName === 'LEGEND' ? l.parentElement : l.parentElement.parentElement;
                    if(!container) continue;

                    let radios = container.querySelectorAll("input[type='radio']");
                    if(radios.length > 0) {{
                        if (!container.id) container.id = "custom_id_" + Math.random().toString(36).substr(2, 9);
                        found.push('RADIO:[id="' + container.id + '"]');
                    }}
                    let combo = container.querySelector("input[role='combobox'], input[aria-autocomplete='list']");
                    if(combo) {{
                        if (!combo.id) combo.id = "custom_id_" + Math.random().toString(36).substr(2, 9);
                        found.push('[id="' + combo.id + '"]');
                    }}
                    let sel = container.querySelector("select");
                    if(sel) {{
                        if (!sel.id) sel.id = "custom_id_" + Math.random().toString(36).substr(2, 9);
                        found.push('SELECT:[id="' + sel.id + '"]');
                    }}
                    // Normal text inputs
                    let inp = container.querySelector("input[type='text'], input:not([type]), input[type='tel'], input[type='email']");
                    if(inp && !combo && radios.length === 0) {{
                        if (!inp.id) inp.id = "custom_id_" + Math.random().toString(36).substr(2, 9);
                        found.push('INPUT:[id="' + inp.id + '"]');
                    }}
                }}
            }}
            return found;
        }}""", label_clean)

        if not selectors:
            log.warning(f"   ⚠️ Could not find element for label: {label_clean}")
            failed.append(label_clean)
            return

        for selector in selectors:
            if selector.startswith("SELECT:"):
                page.locator(selector.replace("SELECT:", "")).select_option(label=re.compile(f"^{answer}$", re.IGNORECASE))
                filled.append(label_clean)
                log.info(f"   ✅ [NATIVE SELECT] {label_clean} → {answer}")
                return
            elif selector.startswith("INPUT:"):
                page.locator(selector.replace("INPUT:", "")).fill(answer)
                filled.append(label_clean)
                log.info(f"   ✅ [TEXT INPUT] {label_clean} → {answer}")
                return
            elif selector.startswith("RADIO:"):
                container = page.locator(selector.replace("RADIO:", ""))
                option_labels = container.locator("label")
                answer_norm = answer.strip().lower()
                matched_index = None
                # Pass 1: exact match on the individual option's own label text
                for i in range(option_labels.count()):
                    if option_labels.nth(i).inner_text().strip().lower() == answer_norm:
                        matched_index = i
                        break
                # Pass 2: partial/contains match, for phrasing that doesn't line up exactly
                if matched_index is None:
                    for i in range(option_labels.count()):
                        opt_text = option_labels.nth(i).inner_text().strip().lower()
                        if opt_text and (answer_norm in opt_text or opt_text in answer_norm):
                            matched_index = i
                            break
                if matched_index is not None:
                    option_labels.nth(matched_index).click(force=True)
                    filled.append(label_clean)
                    log.info(f"   ✅ [RADIO] {label_clean} → {answer}")
                    return
                # Pass 3: match on the radio input's own value attribute directly
                radio_inputs = container.locator("input[type='radio']")
                for i in range(radio_inputs.count()):
                    val = (radio_inputs.nth(i).get_attribute("value") or "").strip().lower()
                    if val == answer_norm:
                        radio_inputs.nth(i).check(force=True)
                        filled.append(label_clean)
                        log.info(f"   ✅ [RADIO value] {label_clean} → {answer}")
                        return
                log.warning(f"   ⚠️ Radio group found for '{label_clean}' but no option matched answer '{answer}'")
            else:
                loc = page.locator(selector)
                loc.click(force=True)
                import time
                time.sleep(0.5)

                if "location" in label_clean.lower() or "country" in label_clean.lower():
                    loc.type(answer, delay=20)
                    time.sleep(2)
                    first_opt = page.locator("div[role='option']").first
                    if first_opt.count() > 0:
                        opt_text = first_opt.inner_text()
                        if _option_plausibly_matches(opt_text, answer):
                            first_opt.click(force=True)
                            filled.append(label_clean)
                            log.info(f"   ✅ [AUTOCOMPLETE] {label_clean} → {answer}")
                            return
                        log.warning(f"   ⚠️ Autocomplete's top suggestion ('{opt_text}') doesn't resemble answer '{answer}' for {label_clean} — refusing to force-select it.")

                option = page.locator(f"div[role='option']:has-text('{answer}')").first
                if option.count() > 0:
                    option.click(force=True)
                    filled.append(label_clean)
                    log.info(f"   ✅ [COMBOBOX CLICK] {label_clean} → {answer}")
                    return
                else:
                    loc.type(answer, delay=20)
                    time.sleep(1)
                    first_opt = page.locator("div[role='option']").first
                    if first_opt.count() > 0 and _option_plausibly_matches(first_opt.inner_text(), answer):
                        first_opt.click(force=True)
                        filled.append(label_clean)
                        log.info(f"   ✅ [COMBOBOX TYPE+CLICK] {label_clean} → {answer}")
                        return

    except Exception as e:
        log.error(f"Error evaluating {label_clean}: {e}")

    log.warning(f"   ⚠️ Could not fill: {label_clean} → {answer}")
    failed.append(label_clean)


# Off by default: this path is prototyped and logically sound (built from
# real_apply.py, a working proof-of-concept that submitted one real
# application this way) but has not been verified end-to-end against a live
# Greenhouse board with real OTP/S3-upload timing from this codebase. Turn on
# deliberately once you've confirmed it against a real, low-stakes job —
# don't flip it on for the full queue on faith.
ENABLE_DIRECT_POST_SUBMIT = os.environ.get("ENABLE_DIRECT_POST_SUBMIT", "false").lower() == "true"


def try_direct_post_submit(job_url, answers, resume_bytes, resume_filename):
    """
    Attempt to submit via a direct HTTP POST to Greenhouse's embedded-form
    endpoint instead of driving a full browser — the same approach
    real_apply.py proved out for one candidate. Trades ~90s+ of Playwright
    (page load, 60s resume-upload sleep, OTP wait) for a couple of HTTP
    requests, when it works.

    Returns one of:
      - {"outcome": "success", "confirmation_url": ..., "confirmation_text": ...}
      - {"outcome": "validation_error", "confirmation_text": ...}
      - {"outcome": "submitted_unknown", "confirmation_text": ..., "reason": ...}
                 → the POST was actually sent to Greenhouse and we can't tell
                 whether it succeeded (an OTP screen came back, the response
                 was ambiguous, or reading the response itself failed).
                 CRITICAL: the caller must NEVER fall back to the Playwright
                 browser flow for this outcome — retrying via a different
                 method after a real submission may already have landed
                 would double-apply the candidate to a real job. Route to
                 human review instead.
      - None   → nothing was ever sent to Greenhouse (no form token found, or
                 the request failed before the POST) — genuinely safe to
                 retry via the full Playwright flow.
    """
    session = requests.Session()
    session.proxies = {"http": _proxy_url(), "https": _proxy_url()}
    post_sent = False

    try:
        from bs4 import BeautifulSoup
        resp = session.get(job_url, allow_redirects=True, timeout=20)
        soup = BeautifulSoup(resp.text, "html.parser")

        token_input = soup.find("input", {"name": "mapped_url_token"})
        form_tag = soup.find("form", id="application_form")
        if not token_input or not form_tag:
            log.info("   ⚡ Direct-POST: no embedded application form found — falling back to browser.")
            return None

        form_data = {"mapped_url_token": token_input["value"]}
        for item in answers:
            field_name = item.get("field_name")
            answer = item.get("answer", "")
            if not field_name or field_name == "demographic_question":
                continue  # demographic_question is a synthetic name applywizz_brain uses, not a real form field
            if not answer or answer in ("AI_PLACEHOLDER", "NEEDS_AI"):
                continue
            form_data[field_name] = answer

        files = {}
        if resume_bytes:
            files["resume"] = (resume_filename, resume_bytes, "application/pdf")

        submit_url = f"https://boards.greenhouse.io{form_tag['action']}"
        post_sent = True  # from this point on, never return None — that would trigger a resubmit
        submit_resp = session.post(submit_url, data=form_data, files=files, timeout=30, allow_redirects=True)

        text = submit_resp.text.lower()
        otp_keywords = ['verification code', 'security code', '8-character', 'confirm you', 'enter the code']
        if any(kw in text for kw in otp_keywords):
            log.warning("   ⚡ Direct-POST: form was accepted and now needs an OTP this path can't solve — routing to human review instead of resubmitting.")
            return {"outcome": "submitted_unknown", "confirmation_text": submit_resp.text[:1000], "reason": "otp_required_after_direct_post"}

        if "confirmation" in submit_resp.url or "application_submitted" in submit_resp.url or "thank_you" in submit_resp.url:
            return {"outcome": "success", "confirmation_url": submit_resp.url, "confirmation_text": submit_resp.text[:1000]}
        if "application" in text and ("received" in text or "submitted" in text):
            return {"outcome": "success", "confirmation_url": submit_resp.url, "confirmation_text": submit_resp.text[:1000]}
        if "is required" in text or "invalid" in text or submit_resp.status_code >= 400:
            return {"outcome": "validation_error", "confirmation_text": submit_resp.text[:1000]}

        log.warning("   ⚡ Direct-POST: form was submitted but the response was ambiguous — routing to human review instead of resubmitting.")
        return {"outcome": "submitted_unknown", "confirmation_text": submit_resp.text[:1000], "reason": "ambiguous_response"}

    except Exception as e:
        if post_sent:
            log.warning(f"   ⚡ Direct-POST: form was submitted but reading the response failed ({e}) — routing to human review instead of resubmitting.")
            return {"outcome": "submitted_unknown", "confirmation_text": "", "reason": f"exception_after_post: {e}"}
        log.warning(f"   ⚡ Direct-POST attempt failed before any submission ({e}) — falling back to browser.")
        return None


def _proxy_url():
    return f"http://{PROXY_CONFIG['username']}:{PROXY_CONFIG['password']}@{PROXY_CONFIG['server'].replace('http://', '')}"


def process_job(job):
    job_id = job['id']
    job_url = job['url']
    applywizz_id = job.get('applywizz_id', 'unknown')
    app_data = job.get('application_data') or {}
    answers = app_data.get('answer_map', [])
    company_name = get_company_name_from_url(job_url)
    submit_start_ts = int(time.time() * 1000)

    log.info("=" * 60)
    log.info(f"💪 MUSCLE EXECUTING JOB [{job_id}] for {applywizz_id}")
    log.info(f"URL: {job_url}")
    supabase.table("job_queue").update({"status": "FILLING", "error_message": None}).eq("id", job_id).execute()

    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    filled, failed, skipped = [], [], []

    # Extract resume URL and candidate email from answer map
    resume_url = None
    candidate_email = None
    for a in answers:
        lbl = a.get('label', a.get('question_label', '')).lower()
        if 'resume' in lbl or 'cv' in lbl:
            if a.get('answer') and a['answer'].startswith('http'):
                resume_url = a['answer']
        if 'email' in lbl and a.get('answer'):
            candidate_email = a['answer']

    if not candidate_email:
        # This job's own question labels didn't happen to contain the word
        # "email" (e.g. custom-worded questions) — fall back to the
        # candidate's actual profile instead of leaving this silently None,
        # which used to skip OTP/confirmation checking with no warning and
        # leave the job stuck at SUBMITTED_EMAIL_PENDING forever.
        try:
            profile_resp = supabase.table("candidate_profiles").select("profile_json").eq("applywizz_id", applywizz_id).execute()
            if profile_resp.data:
                client = (profile_resp.data[0].get("profile_json") or {}).get("client", {})
                candidate_email = client.get("company_email") or client.get("personal_email")
                if candidate_email:
                    log.info(f"   ℹ️ candidate_email not found in this job's answers — used candidate_profiles instead: {applywizz_id}")
        except Exception as e:
            log.warning(f"   Could not look up candidate_profiles for email fallback: {e}")

    if not candidate_email:
        log.warning(f"   ⚠️ No candidate_email found anywhere for job [{job_id}] ({applywizz_id}) — OTP and confirmation checks will be skipped for this job.")

    # FIX 3: Extract actual filename from S3 URL instead of hardcoding
    resume_bytes = None
    resume_filename = "resume.pdf"
    if resume_url and resume_url.startswith('http'):
        resume_filename = resume_url.split('/')[-1].split('?')[0]
        resume_bytes = download_resume(resume_url)
    if not resume_bytes:
        supabase.table("job_queue").update({
            "status": "VALIDATION_FAILED",
            "error_message": "Missing or invalid resume; refusing to submit"
        }).eq("id", job_id).execute()
        return

    # ── Try the fast path first: direct HTTP POST, no browser ──
    if ENABLE_DIRECT_POST_SUBMIT:
        log.info("⚡ Attempting direct-POST submission (no browser)...")
        result = try_direct_post_submit(job_url, answers, resume_bytes, resume_filename)
        if result and result["outcome"] == "validation_error":
            supabase.table("job_queue").update({
                "status": "VALIDATION_FAILED",
                "error_message": "Direct-POST submission returned a validation error.",
                "application_data": {**app_data, "proof": {"confirmation_text": result["confirmation_text"]}},
            }).eq("id", job_id).execute()
            log.error(f"❌ Job [{job_id}] VALIDATION_FAILED via direct-POST.")
            return
        if result and result["outcome"] == "success":
            log.info("✅ Direct-POST submission completed. Waiting for Zoho confirmation email...")
            proof = {
                "confirmation_url": result["confirmation_url"],
                "confirmation_text": result["confirmation_text"],
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "method": "direct_post",
            }
            app_data["proof"] = proof
            supabase.table("job_queue").update({
                "status": "SUBMITTED_EMAIL_PENDING",
                "error_message": None,
                "application_data": app_data,
            }).eq("id", job_id).execute()
            if candidate_email and confirmation_email_received(candidate_email, company_name, submit_start_ts):
                elapsed_seconds = int(time.time() - submit_start_ts / 1000)
                started_at_label = time.strftime("%H:%M:%S", time.localtime(submit_start_ts / 1000))
                supabase.table("job_queue").update({
                    "status": "VERIFIED_APPLIED",
                    "error_message": None,
                    "application_data": app_data,
                    "approved_answer_map": {
                        "started_at": started_at_label,
                        "time_taken": f"{elapsed_seconds}s",
                        "email": candidate_email,
                    }
                }).eq("id", job_id).execute()
                log.info(f"🎉 Job [{job_id}] marked as VERIFIED_APPLIED via direct-POST.")
            else:
                log.warning(f"Job [{job_id}] remains SUBMITTED_EMAIL_PENDING (direct-POST).")
            return
        if result and result["outcome"] == "submitted_unknown":
            # The POST was actually sent to Greenhouse — never fall back to
            # the browser here, that would risk a real second submission.
            supabase.table("job_queue").update({
                "status": "SUBMISSION_UNKNOWN",
                "error_message": f"Direct-POST was sent but outcome is unclear ({result.get('reason')}); refusing to resubmit via browser. Needs human review.",
                "application_data": {**app_data, "proof": {"confirmation_text": result["confirmation_text"], "method": "direct_post"}},
            }).eq("id", job_id).execute()
            log.error(f"❌ Job [{job_id}] SUBMISSION_UNKNOWN via direct-POST — not retrying.")
            return
        # result is None → nothing was ever sent to Greenhouse, genuinely
        # safe to fall through to the proven Playwright path below.
        log.info("⚡ Direct-POST inconclusive — falling back to full browser submission.")

    with sync_playwright() as p:
        try:
            log.info("🌐 Launching local Playwright browser...")

            browser = p.chromium.launch(headless=True)

            # FIX 1: DataImpulse Residential Proxy — properly set in new_context
            context = browser.new_context(
                viewport={"width": 1280, "height": 900},
                proxy=PROXY_CONFIG
            )
            log.info(f"🛡️ DataImpulse Residential Proxy ACTIVE: {PROXY_CONFIG['server']}")

            page = context.new_page()

            # Block unnecessary resources BEFORE navigating (saves proxy bandwidth)
            page.route('**/*', block_resources)

            # ── Step 1: Navigate ──
            log.info(f"🚀 Navigating to {job_url}...")
            page.goto(job_url, wait_until="domcontentloaded", timeout=90000)
            page.wait_for_timeout(2000)  # React mount delay


            select_us_country_code(page)

            # ── Step 2: Upload Resume ──
            if resume_bytes:
                try:
                    log.info(f"📎 Uploading resume: {resume_filename}")
                    file_input = page.locator("input[type=file]").first
                    file_input.set_input_files({
                        "name": resume_filename,  # FIX 3: use actual filename
                        "mimeType": "application/pdf",
                        "buffer": resume_bytes
                    })
                    log.info("⏳ Waiting for S3 presigned upload...")
                    page.wait_for_timeout(60000)
                    filled.append("Resume/CV")
                except Exception as e:
                    log.error(f"Resume upload failed: {e}")
                    failed.append("Resume/CV")

            # ── Step 3: Fill all fields using smart label-based detection ──
            for item in answers:
                label = item.get('label', item.get('question_label', ''))
                answer = item.get('answer', '')
                resolver = item.get('resolver', item.get('matched_by', ''))
                status = item.get('status', '')

                # Skip file fields (handled above)
                if any(k in label.lower() for k in ['resume', '/cv', 'cover letter']):
                    continue

                # Skip if no answer
                if not answer or not answer.strip():
                    skipped.append(label)
                    continue

                # Skip AI placeholders
                if answer in ['AI_PLACEHOLDER', 'NEEDS_AI']:
                    failed.append(f"{label} (needs AI)")
                    continue

                smart_fill_field(page, label, answer, filled, failed)

            # ── Step 4: Pre-Submit Screenshot ──
            log.info("📸 Taking pre-submit screenshot...")
            presubmit_path = os.path.join(SCREENSHOT_DIR, f"presubmit_job_{job_id}.png")
            page.screenshot(path=presubmit_path, full_page=True)
            log.info(f"   Saved: {presubmit_path}")
            log.info(f"   Fields filled: {len(filled)} | Failed: {len(failed)} | Skipped: {len(skipped)}")

            # FORCE CLEAR FAILED FOR TEST
            # failed = []

            if failed:

                log.warning(f"   Failed fields: {failed}")
                log.error("❌ Refusing to submit because required fields failed.")
                raise Exception(f"Failed to fill required fields: {failed}")

            # ── Step 5: Submit ──
            log.info("🚀 Clicking Submit Application...")
            try:
                submit_btn = page.locator("button:has-text('Submit Application')").first
                submit_btn.click(timeout=5000)
                log.info("⏳ Waiting 8s for submission to process...")
                page.wait_for_timeout(8000)
            except Exception as e:
                log.error(f"Submit button not found: {e}")
                raise e

            # ── Step 6: REAL Success Detection ──
            page.wait_for_load_state("domcontentloaded", timeout=10000)
            page_text = page.inner_text("body").lower()

            # Check for OTP / security code screen
            otp_keywords = ['verification code', 'security code', '8-character', 'confirm you', 'enter the code', 'check your email']
            if any(kw in page_text for kw in otp_keywords):
                log.warning("🔑 OTP screen detected! Calling Zoho Mail Reader to get the code...")
                if candidate_email:
                    otp = get_otp_from_zoho(candidate_email, company_name, submit_start_ts)
                    if otp:
                        # Fill OTP boxes (could be 8 separate boxes)
                        inputs = page.locator("input[type='text']").all()
                        code_inputs = [inp for inp in inputs if inp.get_attribute("maxlength") == "1"]
                        if not code_inputs:
                            code_inputs = inputs

                        for i, char in enumerate(otp):
                            if i < len(code_inputs):
                                code_inputs[i].fill(char)
                        page.wait_for_timeout(500)
                        # Submit again
                        submit_again = page.locator("button:has-text('Submit'), button:has-text('Verify'), button:has-text('Confirm')").first
                        submit_again.click(timeout=5000)
                        page.wait_for_timeout(8000)
                        page_text = page.inner_text("body").lower()
                        log.info("✅ OTP submitted!")
                    else:
                        supabase.table("job_queue").update({
                            "status": "OTP_TIMEOUT",
                            "error_message": "OTP required but not received from Zoho"
                        }).eq("id", job_id).execute()
                        return

            # Final success check (STRICT)
            # URL changes OR the application form disappears completely, plus known text.
            final_path = os.path.join(SCREENSHOT_DIR, f"final_job_{job_id}.png")
            page.screenshot(path=final_path, full_page=True)
            confirmation_url = page.url
            confirmation_text = page_text[:1000]

            is_success = False
            is_validation_error = False

            # Specific confirmation phrases only — the previous check ("application"
            # + "received"/"submitted" appearing anywhere on the page) could
            # false-positive on unrelated boilerplate/disclaimer text and mark a
            # job SUBMITTED_EMAIL_PENDING (which the dashboard counts as
            # "Completed") without a real submission ever happening.
            CONFIRMATION_PHRASES = [
                "thank you for applying",
                "your application has been received",
                "we have received your application",
                "application submitted successfully",
                "your application was submitted",
            ]
            if "confirmation" in page.url or "application_submitted" in page.url or "thank_you" in page.url:
                is_success = True
            elif page.locator("#application-form").count() == 0 and any(p in page_text for p in CONFIRMATION_PHRASES):
                is_success = True
            else:
                # Check for visible validation errors
                if page.locator(".field-with-errors").count() > 0 or "is required" in page_text or "invalid" in page_text:
                    is_validation_error = True

            # Capture proof and free the browser slot immediately — the Zoho
            # confirmation poll below can take up to 10 minutes, and there's no
            # reason to hold a headless Chromium instance open for that; every
            # extra minute a worker sits idle is a job another candidate is
            # waiting behind.
            browser.close()

            proof = {
                "confirmation_url": confirmation_url,
                "confirmation_text": confirmation_text,
                "final_screenshot_path": final_path,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
            app_data["proof"] = proof

            if is_success:
                log.info("✅ Browser submission completed. Waiting for Zoho confirmation email...")
                supabase.table("job_queue").update({
                    "status": "SUBMITTED_EMAIL_PENDING",
                    "error_message": None,
                    "application_data": app_data,
                }).eq("id", job_id).execute()
                if candidate_email and confirmation_email_received(candidate_email, company_name, submit_start_ts):
                    elapsed_seconds = int(time.time() - submit_start_ts / 1000)
                    started_at_label = time.strftime("%H:%M:%S", time.localtime(submit_start_ts / 1000))
                    supabase.table("job_queue").update({
                        "status": "VERIFIED_APPLIED",
                        "error_message": None,
                        "application_data": app_data,
                        # Real per-job telemetry only — this must never be filled with
                        # placeholder/templated values (that's what misled the dashboard before).
                        "approved_answer_map": {
                            "started_at": started_at_label,
                            "time_taken": f"{elapsed_seconds}s",
                            "email": candidate_email,
                        }
                    }).eq("id", job_id).execute()
                    log.info(f"🎉 Job [{job_id}] marked as VERIFIED_APPLIED in Supabase.")
                else:
                    log.warning(f"Job [{job_id}] remains SUBMITTED_EMAIL_PENDING.")
                log.info(f"📊 Final Score — Filled: {len(filled)} | Failed: {len(failed)} | Skipped: {len(skipped)}")
            elif is_validation_error or page.locator("button:has-text('Submit Application')").count() > 0:
                log.error("❌ Form still showing or validation errors present after submit!")
                supabase.table("job_queue").update({
                    "status": "VALIDATION_FAILED",
                    "error_message": "Form was not submitted; validation errors present. Check screenshot.",
                    "application_data": app_data,
                }).eq("id", job_id).execute()
            else:
                # Clicked submit, but nothing on the page confirms it went through
                # and nothing indicates a validation error either — an honest
                # "we don't know" status distinct from ERROR, per the no-unproven-
                # success rule: never claim VERIFIED_APPLIED or SUBMITTED_EMAIL_PENDING
                # without actual evidence.
                log.error("❌ Unknown post-submit state — no confirmation evidence found.")
                supabase.table("job_queue").update({
                    "status": "SUBMISSION_UNKNOWN",
                    "error_message": "Clicked submit but found no confirmation evidence on the resulting page.",
                    "application_data": app_data,
                }).eq("id", job_id).execute()

        except Exception as e:
            log.error(f"💥 Critical error processing job [{job_id}]: {e}")
            if 'browser' in locals():
                try:
                    browser.close()
                except Exception:
                    pass

            supabase.table("job_queue").update({
                "status": "ERROR",
                "error_message": str(e)
            }).eq("id", job_id).execute()
            log.error(f"Job [{job_id}] marked as ERROR.")


# The SELECT+UPDATE fallback below has a race: two workers can both read the
# same APPROVED row before either flips its status, and both submit it. Safe
# with exactly one worker; unsafe with the multiple Railway replicas we run
# in production. Only opt into it explicitly (e.g. a single local dev run
# without the RPC deployed) — never let it happen silently under scale.
ALLOW_UNSAFE_CLAIM_FALLBACK = os.environ.get("ALLOW_UNSAFE_CLAIM_FALLBACK", "false").lower() == "true"


def claim_next_job():
    try:
        res = supabase.rpc("claim_next_approved_job", {"worker_id": WORKER_ID}).execute()
        if res.data:
            return res.data[0]
        return None
    except Exception as e:
        if not ALLOW_UNSAFE_CLAIM_FALLBACK:
            log.error(
                f"💥 claim_next_approved_job RPC failed: {e}. Refusing to fall back to the "
                "non-atomic claim query because it double-submits jobs under concurrent "
                "workers. Skipping this cycle — fix the RPC (see 01_claim_next_approved_job.sql) "
                "or set ALLOW_UNSAFE_CLAIM_FALLBACK=true if you are intentionally running a "
                "single worker without it."
            )
            return None
        log.warning(f"RPC claim failed, using single-worker fallback (UNSAFE for >1 worker): {e}")

    res = supabase.table("job_queue").select("*").eq("status", "APPROVED").order("created_at").limit(1).execute()
    if not res.data:
        return None
    job = res.data[0]
    supabase.table("job_queue").update({"status": "CLAIMED", "error_message": None}).eq("id", job["id"]).eq("status", "APPROVED").execute()
    return job


def run_muscle_worker():
    while True:
        log.info("💪 MUSCLE: Checking for APPROVED jobs...")
        try:
            job = claim_next_job()
            if not job:
                log.info("No APPROVED jobs found. Sleeping 15s...")
                time.sleep(15)
                continue

            process_job(job)

        except Exception as e:
            log.error(f"Muscle loop error: {e}")
            time.sleep(15)


if __name__ == '__main__':
    run_muscle_worker()
