import os
import time
import requests
import tempfile
import re
from supabase import create_client
from playwright.sync_api import sync_playwright

# --- CONFIG ---
SUPABASE_URL = "https://lnlvxsskkxeidlqgqqrj.supabase.co"
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo") 
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

ZOHO_API = "https://zoho-mail-reader.onrender.com/api/zoho/messages"
PROXY = {
    "server": "http://gw.dataimpulse.com:823",
    "username": os.environ.get("PROXY_USERNAME", "7dfdbfd6f547946ba484"),
    "password": os.environ.get("PROXY_PASSWORD", "64b2edaac0ebaf3e")
}

def get_zoho_otp(email_address):
    print(f"  🔑 Polling Zoho for Greenhouse OTP for {email_address}...")
    for _ in range(12): 
        try:
            r = requests.get(f"{ZOHO_API}?email={email_address}&limit=5")
            if r.status_code == 200:
                msgs = r.json().get("data", [])
                for m in msgs:
                    subj = m.get("subject", "").lower()
                    if "verification code" in subj or "verify your email" in subj:
                        match = re.search(r'\b\d{8}\b', m.get("text", ""))
                        if match:
                            return match.group(0)
        except Exception:
            pass
        time.sleep(15)
    return None

def check_final_email(email_address, company_keyword):
    print(f"  📧 Polling Zoho for 'Thank you for applying' from {company_keyword}...")
    for _ in range(12):
        try:
            r = requests.get(f"{ZOHO_API}?email={email_address}&limit=5")
            if r.status_code == 200:
                msgs = r.json().get("data", [])
                for m in msgs:
                    subj = m.get("subject", "").lower()
                    if "thank you for applying" in subj or "application received" in subj:
                        return True
        except Exception:
            pass
        time.sleep(15)
    return False

def execute_dynamic_application(job_row, page):
    answers = job_row.get("approved_answer_map", {})
    applywizz_id = job_row.get("applywizz_id")
    target_email = answers.get("email")

    if not target_email:
        raise Exception("VALIDATION_FAILED: No email found in approved_answer_map.")

    # 1. STRICT RESUME VALIDATION
    resume_url = answers.get("resume_url")
    if not resume_url:
        raise Exception("VALIDATION_FAILED: No resume URL found.")

    print(f"  ⬇️ Downloading Resume from S3 for {applywizz_id}...")
    pdf_resp = requests.get(resume_url, timeout=10)
    if pdf_resp.status_code != 200 or len(pdf_resp.content) < 5000:
        raise Exception(f"VALIDATION_FAILED: S3 Download failed. Status: {pdf_resp.status_code}")

    tmp_pdf = tempfile.mktemp(suffix=".pdf")
    with open(tmp_pdf, 'wb') as f:
        f.write(pdf_resp.content)

    # 2. DYNAMIC STANDARD FIELDS
    print("  📝 Filling Standard Fields dynamically...")
    if page.locator("input[id='first_name']").count() > 0:
        page.locator("input[id='first_name']").fill(answers.get("first_name", ""))
        page.locator("input[id='last_name']").fill(answers.get("last_name", ""))
        page.locator("input[id='email']").fill(target_email)

    # 3. COUNTRY CODE & PHONE
    phone = answers.get("phone", "")
    if phone and page.locator("input[id='phone']").count() > 0:
        print("  📞 Selecting Country Code and filling phone...")
        if page.locator(".iti__selected-flag").count() > 0:
            page.locator(".iti__selected-flag").click()
            page.locator("li[data-country-code='us']").click()
        page.locator("input[id='phone']").fill(phone)

    # 4. SECURE RESUME UPLOAD
    print("  📄 Uploading Resume to Greenhouse (10s wait)...")
    if page.locator("input[type='file']").count() > 0:
        page.locator("input[type='file']").first.set_input_files(tmp_pdf)
        page.wait_for_timeout(10000) 

    # 5. DYNAMIC CUSTOM QUESTIONS
    print("  🧠 Processing Job-Specific Custom Questions...")
    custom_questions = answers.get("custom_questions", [])
    for q in custom_questions:
        field_id = q.get("field_id")
        field_type = q.get("field_type")
        ai_answer = q.get("answer")
        
        if field_id and ai_answer:
            if field_type in ["input_text", "textarea"]:
                page.locator(f"[id='{field_id}']").fill(str(ai_answer))
            elif field_type == "dropdown":
                page.locator(f"select[id='{field_id}']").select_option(label=str(ai_answer))

    # 6. CONSENT CHECKBOXES
    print("  ⚖️ Checking consent boxes...")
    consent_boxes = page.locator("input[type='checkbox']")
    for i in range(consent_boxes.count()):
        consent_boxes.nth(i).check(force=True)

    os.remove(tmp_pdf)
    print("  ✅ Form completely filled dynamically.")

def run_production_worker():
    print("🚀 Worker started. Continuously listening for APPROVED jobs...")
    while True:
        try:
            res = supabase.table("job_queue").select("*").eq("status", "APPROVED").order("created_at", desc=False).limit(1).execute()
            jobs = res.data
            if not jobs:
                time.sleep(10)
                continue
                
            job = jobs[0]
            job_id = job["id"]
            job_url = job["url"]
            company_name = job_url.split("job-boards.greenhouse.io/")[1].split("/")[0] if "greenhouse.io" in job_url else "Company"
            
            print(f"\n⚡ Claimed job {job_id} for {company_name} ({job_url})")
            supabase.table("job_queue").update({"status": "CLAIMED"}).eq("id", job_id).execute()

            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                context = browser.new_context(proxy=PROXY, viewport={"width": 1280, "height": 900})
                page = context.new_page()
                
                try:
                    page.goto(job_url, timeout=60000)
                    page.wait_for_load_state("networkidle")
                    supabase.table("job_queue").update({"status": "FILLING"}).eq("id", job_id).execute()
                    
                    # RUN DYNAMIC CORE
                    execute_dynamic_application(job, page)
                    
                    print("  🖱️ Clicking Initial Submit...")
                    page.locator("button#submit_app, input#submit_app, input[type='submit']").first.click(force=True)
                    time.sleep(5)
                    
                    # OTP CHECKER
                    if page.locator("text=A verification code was sent").count() > 0 or page.locator("input[aria-label='Digit 1']").count() > 0:
                        print("  🛑 Greenhouse OTP Challenge Detected!")
                        target_email = job.get("approved_answer_map", {}).get("email")
                        otp_code = get_zoho_otp(target_email)
                        if otp_code:
                            print(f"  ✅ Extracted OTP: {otp_code}")
                            for i in range(8):
                                page.locator(f"input[aria-label='Digit {i+1}']").fill(otp_code[i])
                            print("  🖱️ Submitting OTP...")
                            if page.locator("button:has-text('Submit application')").count() > 0:
                                page.locator("button:has-text('Submit application')").click(force=True)
                                time.sleep(5)
                        else:
                            raise Exception("OTP Timeout")

                    supabase.table("job_queue").update({"status": "SUBMITTED_EMAIL_PENDING"}).eq("id", job_id).execute()
                    
                    target_email = job.get("approved_answer_map", {}).get("email")
                    if check_final_email(target_email, company_name):
                        supabase.table("job_queue").update({"status": "VERIFIED_APPLIED"}).eq("id", job_id).execute()
                        print("  🟢 SUCCESS: Database marked as VERIFIED_APPLIED!")
                    else:
                        print("  🔴 Final confirmation email not received. Leaving as EMAIL_PENDING.")
                        
                except Exception as e:
                    print(f"  ❌ Error executing job: {e}")
                    supabase.table("job_queue").update({"status": "ERROR", "error_message": str(e)}).eq("id", job_id).execute()
                finally:
                    browser.close()

            print("⏳ Cooldown: Waiting 3 minutes before checking next job...")
            time.sleep(180)

        except Exception as loop_err:
            print(f"⚠️ Worker loop warning: {loop_err}")
            time.sleep(10)

if __name__ == "__main__":
    run_production_worker()
