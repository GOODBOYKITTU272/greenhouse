"""
ApplyWizz MUSCLE WORKER — Phase 4: Database-Driven Execution Engine
=========================================================
Reads APPROVED jobs from Supabase job_queue and executes
the form fill on Browserless cloud using Playwright.
"""

import json
import logging
import os
import time
import requests
from playwright.sync_api import sync_playwright
from supabase import create_client

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s',
    datefmt='%H:%M:%S'
)
log = logging.getLogger("MUSCLE")

TOKEN = '2V99YQKs3tXG9xcb10cf2a54b9841059eb9bf8cb5a51e8c24'
WS_URL = f'wss://production-sfo.browserless.io?token={TOKEN}&stealth=true'
SCREENSHOT_DIR = '/Users/ramakrishnachanda/Desktop/greenhosue/screenshots'

# Connect to Supabase
supabase = create_client(
    'https://lnlvxsskkxeidlqgqqrj.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo'
)

def block_resources(route):
    """Cost Optimization: Block images, CSS, fonts, and media to save bandwidth."""
    if route.request.resource_type in ['image', 'stylesheet', 'font', 'media']:
        route.abort()
    else:
        route.continue_()

def download_resume(url):
    log.info(f"Downloading resume from S3: {url}")
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        log.info(f"Resume downloaded: {len(resp.content)} bytes")
        return resp.content
    except Exception as e:
        log.error(f"Resume download failed: {e}")
        return None

def process_job(job):
    job_id = job['id']
    job_url = job['url']
    applywizz_id = job.get('applywizz_id', 'unknown')
    answers = job.get('application_data', [])
    
    log.info("=" * 60)
    log.info(f"💪 MUSCLE EXECUTING JOB [{job_id}] for {applywizz_id}")
    log.info(f"URL: {job_url}")
    
    os.makedirs(SCREENSHOT_DIR, exist_ok=True)
    filled, failed, skipped = [], [], []

    resume_url = None
    for a in answers:
        if a['field_name'] == 'resume' and a.get('answer'):
            resume_url = a['answer']
            break

    resume_bytes = None
    if resume_url and resume_url.startswith('http'):
        resume_bytes = download_resume(resume_url)

    with sync_playwright() as p:
        try:
            log.info("🌐 Connecting to Browserless...")

            log.info("🌐 Connecting to Browserless (Stealth Mode)...")
            browser = p.chromium.connect_over_cdp(WS_URL)
            context = browser.new_context(viewport={"width": 1280, "height": 900})
            page = context.new_page()

            # Block unnecessary resources BEFORE navigating
            page.route('**/*', block_resources)

            # ── Step 1: Navigate ──
            log.info(f"🚀 Navigating to {job_url}...")
            page.goto(job_url, wait_until="load", timeout=45000)
            page.wait_for_timeout(2000)  # React mount delay

            # ── Step 2: Upload Resume ──
            if resume_bytes:
                try:
                    log.info("📎 Uploading resume to hidden file input...")
                    file_input = page.locator("input[type=file]").first
                    file_input.set_input_files({
                        "name": "resume_yakub_ali_mohammed.pdf",
                        "mimeType": "application/pdf",
                        "buffer": resume_bytes
                    })
                    log.info("⏳ Waiting 3000ms for S3 presigned upload...")
                    page.wait_for_timeout(3000)
                    filled.append("Resume/CV")
                except Exception as e:
                    log.error(f"Resume upload failed: {e}")
                    failed.append("Resume/CV")

            # ── Step 3-5: Fill all fields from the answer map ──
            for item in answers:
                label = item['question_label']
                answer = item['answer']
                field_type = item['field_type']
                field_name = item['field_name']
                matched_by = item.get('matched_by', '')

                # Skip file uploads (already handled above)
                if field_type == 'input_file':
                    continue

                # Skip empty/optional answers only if they genuinely have no answer string
                if not answer and matched_by == 'skipped_optional':
                    skipped.append(label)
                    continue

                # Skip AI placeholders (not ready)
                if answer == 'AI_PLACEHOLDER':
                    failed.append(f"{label} (needs AI)")
                    continue

                try:
                    if field_type in ['input_text', 'textarea']:
                        # ── TEXT FIELDS ──
                        label_loc = page.locator("label").filter(has_text=label).first
                        container = label_loc.locator("xpath=../..")
                        input_field = container.locator("input, textarea").first

                        input_field.fill(answer, timeout=3000)
                        filled.append(label)

                        # Special delay after email for async validator
                        if field_name == 'email':
                            log.info(f"   ✅ {label} → {answer} (waiting 1000ms for validator)")
                            page.wait_for_timeout(1000)
                        else:
                            log.info(f"   ✅ {label} → {answer}")
                            page.wait_for_timeout(500)

                    elif field_type == 'multi_value_single_select':
                        # ── DROPDOWN (react-aria or standard select) ──
                        # EEOC questions often use standard <select> tags with the field_name in the name attribute
                        select_loc = page.locator(f"select[name*='{field_name}']")
                        
                        if select_loc.count() > 0:
                            # It's a standard select tag!
                            select_loc.first.select_option(label=answer, timeout=3000)
                            page.wait_for_timeout(500)
                            filled.append(label)
                            log.info(f"   ✅ {label} → {answer} (standard select)")
                        else:
                            # It's a custom React combobox
                            label_loc = page.locator("label").filter(has_text=label).first
                            container = label_loc.locator("xpath=../..")

                            # Find and click the "Toggle flyout" button (Force click bypasses overlapping iframes)
                            flyout_btn = container.locator("button").last
                            flyout_btn.click(timeout=3000, force=True)
                            page.wait_for_timeout(800)  # React dropdown animation

                            # Click the exact option from the dropdown
                            option = page.locator("[role='option']").filter(has_text=answer).first
                            option.click(timeout=3000, force=True)
                            page.wait_for_timeout(500)

                            filled.append(label)
                            log.info(f"   ✅ {label} → {answer} (react dropdown)")

                    elif field_type in ['multi_value_multi_select', 'multi_value_multi_select_other']:
                        # ── CHECKBOXES (select all that apply) ──
                        # Answer from Brain is comma-separated: "Excel, SQL, Python"
                        selected_options = [o.strip() for o in answer.split(',') if o.strip() and o.strip().lower() not in ['n/a', 'none', '']]
                        for opt_label in selected_options:
                            try:
                                # Find the checkbox by its label text and click it
                                cb = page.locator(f"label:has-text('{opt_label}')").first
                                if cb.count() > 0:
                                    cb.click(timeout=3000, force=True)
                                    page.wait_for_timeout(300)
                                    log.info(f"   ✅ {label} → checked: {opt_label}")
                                else:
                                    # Try finding by input[type=checkbox] near the text
                                    cb2 = page.locator(f"text='{opt_label}'").locator("xpath=../input[@type='checkbox']")
                                    cb2.check(timeout=3000)
                                    page.wait_for_timeout(300)
                                    log.info(f"   ✅ {label} → checked (input): {opt_label}")
                            except Exception as ce:
                                log.warning(f"   ⚠️ Could not check '{opt_label}': {ce}")
                        filled.append(label)

                except Exception as e:
                    log.error(f"   ❌ {label}: {e}")
                    failed.append(label)

            # ── Step 6: Pre-Submit Snapshot ──
            log.info("📸 Taking pre-submit screenshot...")
            presubmit_path = os.path.join(SCREENSHOT_DIR, f"presubmit_job_{job_id}.png")
            page.screenshot(path=presubmit_path, full_page=True)
            log.info(f"   Saved: {presubmit_path}")

            # ── Step 7: Submit ──
            log.info("🚀 Submitting for real...")
            try:
                submit_btn = page.locator("button:has-text('Submit Application')").first
                submit_btn.click(timeout=5000)
                page.wait_for_timeout(8000)  # wait for submit / captcha / redirect
                log.info("✅ APPLICATION SUBMITTED!")
                
                # ── Step 8: Final Screenshot ──
                final_path = os.path.join(SCREENSHOT_DIR, f"final_job_{job_id}.png")
                page.screenshot(path=final_path, full_page=True)
                
                # Update Supabase to COMPLETED
                supabase.table("job_queue").update({
                    "status": "COMPLETED",
                    "error_message": None
                }).eq("id", job_id).execute()
                log.info(f"🎉 Job [{job_id}] marked as COMPLETED in Supabase.")
                
            except Exception as e:
                log.error(f"Submit button click failed: {e}")
                raise e

            browser.close()

        except Exception as e:
            log.error(f"💥 Critical error processing job [{job_id}]: {e}")
            if 'browser' in locals():
                try: browser.close()
                except: pass
                
            supabase.table("job_queue").update({
                "status": "ERROR",
                "error_message": str(e)
            }).eq("id", job_id).execute()


def run_muscle_worker():
    target_clients = ['AWL-27321', 'AWL-32692', 'AWL-31835', 'AWL-28569', 'AWL-31072']
    while True:
        log.info("💪 MUSCLE: Checking for APPROVED jobs...")
        try:
            response = supabase.table("job_queue").select("*").eq("status", "APPROVED").in_("applywizz_id", target_clients).limit(5).execute()
            jobs = response.data
            
            if not jobs:
                log.info("No APPROVED jobs found. Sleeping 15s...")
                time.sleep(15)
                continue
                
            for job in jobs:
                process_job(job)
                
        except Exception as e:
            log.error(f"Muscle loop error: {e}")
            time.sleep(15)

if __name__ == '__main__':
    run_muscle_worker()

