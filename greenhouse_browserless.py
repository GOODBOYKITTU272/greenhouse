import sys
import os
import requests
import time
from playwright.sync_api import sync_playwright

candidate_json = {
  "client": {
    "full_name": "Yakub Ali Mohammed",
    "company_email": "yakubali.mohammed@applywizard.ai",
    "visa_type": "Other"
  },
  "additional_information": {
    "primary_phone": "+1234567890",
    "linked_in_url": "https://www.linkedin.com/in/yakub-mohammed",
    "resume_url": "https://applywizz-prod.s3.us-east-2.amazonaws.com/CRM/AWL-30453-28072026-0001-resume_yakub-ali-mohammed_ne.pdf"
  }
}

def main():
    job_url = "https://job-boards.greenhouse.io/lendingtree/jobs/8155569?gh_src=zb723m9b1us"
    
    print("Downloading resume from S3...")
    r = requests.get(candidate_json["additional_information"]["resume_url"], verify=False)
    resume_bytes = r.content

    names = candidate_json["client"]["full_name"].split()
    first_name = names[0]
    last_name = " ".join(names[1:])
    email = candidate_json["client"]["company_email"]
    phone = candidate_json["additional_information"]["primary_phone"]
    linkedin = candidate_json["additional_information"]["linked_in_url"]

    with sync_playwright() as p:
        # BROWSERLESS CONNECTION LOGIC
        token = os.environ.get("BROWSERLESS_TOKEN")
        if not token:
            print("ERROR: BROWSERLESS_TOKEN environment variable is missing!")
            print("Please run: export BROWSERLESS_TOKEN='your-key' before running the script.")
            sys.exit(1)
            
        ws_endpoint = f"wss://production-sfo.browserless.io?token={token}"
        print("Connecting to Browserless.io cloud instance...")
        
        # We use connect_over_cdp to leverage stealth features
        browser = p.chromium.connect_over_cdp(ws_endpoint)
        page = browser.new_page()
        
        print(f"Navigating to {job_url}...")
        page.goto(job_url)
        page.wait_for_load_state("networkidle")
        time.sleep(2) # Give React 2 seconds to load
        
        # 1. ATTACH THE RESUME
        try:
            page.locator("#resume").set_input_files([
                {"name": "resume_yakub.pdf", "mimeType": "application/pdf", "buffer": resume_bytes}
            ])
            print("Resume attached successfully.")
        except Exception as e:
            print(f"Error uploading resume: {e}")

        # 2. INJECT THE FLAWLESS JAVASCRIPT
        print("Injecting Javascript bypass for React fields...")
        js_injection = f"""
        (function() {{
            const firstName = "{first_name}";
            const lastName = "{last_name}";
            const email = "{email}";
            const phone = "{phone}";
            const linkedin = "{linkedin}";

            function nativeTypeById(id, text) {{
                const el = document.getElementById(id);
                if (el) {{
                    el.focus();
                    el.select();
                    document.execCommand('insertText', false, text);
                    el.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    el.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                }}
            }}

            nativeTypeById('first_name', firstName);
            nativeTypeById('last_name', lastName);
            nativeTypeById('email', email);
            nativeTypeById('phone', phone);
            
            function fillCustomField(labelText, answerText, isDropdown=false) {{
                const labels = Array.from(document.querySelectorAll('label, .asterisk'));
                const target = labels.find(l => l.innerText && l.innerText.toLowerCase().includes(labelText.toLowerCase()));
                
                if (target) {{
                    const container = target.closest('div');
                    if (container) {{
                        if (isDropdown) {{
                            const input = container.parentElement.querySelector('input[role="combobox"]');
                            if (input) {{
                                input.focus();
                                document.execCommand('insertText', false, answerText);
                                setTimeout(() => {{
                                    input.dispatchEvent(new KeyboardEvent('keydown', {{ key: 'Enter', keyCode: 13, bubbles: true }}));
                                }}, 100);
                            }}
                        }} else {{
                            const input = container.parentElement.querySelector('input[type="text"]');
                            if (input && input.id !== 'first_name') {{ 
                                input.focus();
                                input.select();
                                document.execCommand('insertText', false, answerText);
                            }}
                        }}
                    }}
                }}
            }}

            fillCustomField('LinkedIn', linkedin, false);
            fillCustomField('salary expectations', '100k - 130k', false);
            fillCustomField('hear about this job', 'Company Website', false);

            fillCustomField('worked for our company before', 'No', true);
            fillCustomField('temporary or subject to expiration', 'Yes', true);
            fillCustomField('authorized to work in the United States', 'Yes', true);
            fillCustomField('receive text message updates', 'Yes', true);
            
            fillCustomField('gender identity', 'I prefer not to answer', true);
            fillCustomField('racial/ethnic background', 'I prefer not to answer', true);
            fillCustomField('sexual orientation', 'I prefer not to answer', true);
            fillCustomField('identify as transgender', 'I prefer not to answer', true);
            fillCustomField('disability or chronic condition', 'No', true);
            fillCustomField('veteran or active member', 'I am not a protected veteran', true);
        }})();
        """
        
        page.evaluate(js_injection)
        time.sleep(1) 
        
        # Note: In a true cloud environment, we would click submit here or take a screenshot to verify success.
        # For now, we take a screenshot to prove the cloud browser did its job!
        print("Taking verification screenshot...")
        page.screenshot(path="browserless_success.png", full_page=True)
        print("Screenshot saved to 'browserless_success.png'")

        print("\n--- AUTOFILL COMPLETE ---")
        browser.close()

if __name__ == "__main__":
    main()
