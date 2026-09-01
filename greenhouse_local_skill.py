import sys
import time
import requests
from playwright.sync_api import sync_playwright

candidate = {
    "first_name": "Yakub",
    "last_name": "Ali Mohammed",
    "email": "yakubali.mohammed@applywizard.ai",
    "phone": "1234567890",
    "linkedin": "https://www.linkedin.com/in/yakub-mohammed"
}

def main():
    print("Starting Official Playwright Skill Flow...")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        print("1. Opening LendingTree job page...")
        page.goto("https://job-boards.greenhouse.io/lendingtree/jobs/8155569?gh_src=zb723m9b1us")
        page.wait_for_load_state("networkidle")
        time.sleep(2)

        print("2. Attaching resume natively...")
        resume_bytes = requests.get("https://applywizz-prod.s3.us-east-2.amazonaws.com/CRM/AWL-30453-28072026-0001-resume_yakub-ali-mohammed_ne.pdf", verify=False).content
        page.locator("input[type=file]").first.set_input_files([
            {"name": "resume_yakub.pdf", "mimeType": "application/pdf", "buffer": resume_bytes}
        ])
        time.sleep(1)

        print("3. Filling standard text fields...")
        page.locator("#first_name").fill(candidate["first_name"])
        page.locator("#last_name").fill(candidate["last_name"])
        page.locator("#email").fill(candidate["email"])
        time.sleep(1) # Required wait for async email validator
        page.locator("#phone").fill(candidate["phone"])

        # Combobox Helper Function (The Official Skill Way)
        def fill_combobox(label_text, option_text):
            try:
                label = page.locator(f"label:has-text('{label_text}')").first
                if label.is_visible():
                    container = label.locator("xpath=../..")
                    flyout_btn = container.locator("button").first
                    if flyout_btn.is_visible():
                        flyout_btn.click()
                        time.sleep(0.8) # Wait for React animation
                        page.locator(f"[role='option']:has-text('{option_text}')").first.click()
                        time.sleep(0.2)
            except Exception as e:
                pass

        print("4. Clicking custom dropdowns using the new Skill pattern...")
        fill_combobox("temporary or subject to expiration", "Yes")
        fill_combobox("authorized to work", "Yes")
        fill_combobox("receive text message", "Yes")
        fill_combobox("gender identity", "I prefer not to answer")
        fill_combobox("racial/ethnic background", "I prefer not to answer")
        fill_combobox("sexual orientation", "I prefer not to answer")
        fill_combobox("identify as transgender", "I prefer not to answer")
        fill_combobox("disability or chronic condition", "No")
        fill_combobox("veteran", "I am not a protected veteran")

        try:
            page.locator("label:has-text('LinkedIn')").locator("xpath=../..").locator("input[type='text']").first.fill(candidate["linkedin"])
            page.locator("label:has-text('salary')").locator("xpath=../..").locator("input[type='text']").first.fill("100k - 130k")
        except:
            pass

        print("5. Taking verification screenshot...")
        page.screenshot(path="local_skill_success.png", full_page=True)
        print("\n--- DONE! Screenshot saved as 'local_skill_success.png' ---")
        browser.close()

if __name__ == "__main__":
    main()
