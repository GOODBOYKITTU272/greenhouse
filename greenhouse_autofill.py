import sys
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
    r = requests.get(candidate_json["additional_information"]["resume_url"], verify=False)
    resume_bytes = r.content

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        page.goto(job_url)
        print("Waiting 5 seconds for page load...")
        time.sleep(5)
        
        # Helper function: Click the label text, hit TAB to enter the field, then type
        def fill_by_tabbing(label_text, answer):
            try:
                # Find the label on the screen and click it
                page.locator(f"text='{label_text}'").first.click(force=True)
                time.sleep(0.5)
                # Tab moves focus from the label to the input/dropdown immediately below it
                page.keyboard.press("Tab")
                time.sleep(0.5)
                # Type the answer
                page.keyboard.type(answer, delay=50)
                # Hit enter (selects the dropdown option if it's a combobox)
                page.keyboard.press("Enter")
                time.sleep(0.5)
                print(f"Filled: {label_text}")
            except Exception as e:
                print(f"Failed to fill {label_text}: {e}")

        # Top Fields
        try:
            page.locator("#first_name").focus()
            page.keyboard.type("Yakub", delay=50)
            page.locator("#last_name").focus()
            page.keyboard.type("Ali Mohammed", delay=50)
            page.locator("#email").focus()
            page.keyboard.type("yakubali.mohammed@applywizard.ai", delay=50)
            page.locator("#phone").focus()
            page.keyboard.type("+1234567890", delay=50)
        except: pass

        # Resume
        try:
            page.locator("#resume").set_input_files([{"name": "resume.pdf", "mimeType": "application/pdf", "buffer": resume_bytes}])
        except: pass

        print("Processing bottom questions using Tab-Flow routing...")
        
        # Custom Text Fields
        fill_by_tabbing("LinkedIn Profile", "https://www.linkedin.com/in/yakub-mohammed")
        fill_by_tabbing("How did you hear about this job?", "Company Website")
        fill_by_tabbing("base salary expectations", "100k - 130k")

        # Dropdowns
        fill_by_tabbing("worked for our company before", "No")
        fill_by_tabbing("temporary or subject to expiration", "Yes")
        fill_by_tabbing("authorized to work in the United States", "Yes")
        fill_by_tabbing("receive text message updates", "Yes")
        
        fill_by_tabbing("gender identity", "I prefer not to answer")
        fill_by_tabbing("racial/ethnic background", "I prefer not to answer")
        fill_by_tabbing("sexual orientation", "I prefer not to answer")
        fill_by_tabbing("identify as transgender", "I prefer not to answer")
        fill_by_tabbing("disability or chronic condition", "No")
        fill_by_tabbing("veteran or active member", "I am not a protected veteran")

        print("\n--- AUTOFILL COMPLETE ---")
        input("\nPress ENTER here in the terminal to close the browser...")
        browser.close()

if __name__ == "__main__":
    main()
