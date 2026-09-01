import time
from playwright.sync_api import sync_playwright

URL = "https://job-boards.greenhouse.io/lendingtree/jobs/8155569?gh_src=zb723m9b1us"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL)
    page.wait_for_load_state("networkidle")
    time.sleep(2)

    fields = [("#first_name", "Yakub"), ("#last_name", "Ali Mohammed"),
              ("#email", "yakubali.mohammed@applywizard.ai"), ("#phone", "+1234567890")]
    for sel, val in fields:
        try:
            page.locator(sel).click(force=True)
            page.keyboard.type(val, delay=50)
            print(f"{sel}: typed OK")
        except Exception as e:
            print(f"{sel}: FAILED {type(e).__name__}: {e}")

    readback = page.evaluate("""
        () => ({
          first_name: document.getElementById('first_name')?.value,
          last_name: document.getElementById('last_name')?.value,
          email: document.getElementById('email')?.value,
          phone: document.getElementById('phone')?.value,
        })
    """)
    print("--- actual DOM values ---")
    print(readback)
    browser.close()
