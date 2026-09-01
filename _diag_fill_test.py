import re
from playwright.sync_api import sync_playwright

URL = "https://job-boards.greenhouse.io/lendingtree/jobs/8155569?gh_src=zb723m9b1us"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto(URL)
    page.wait_for_selector("form", timeout=10000)

    results = {}
    for label, value in [
        ("First Name", "Yakub"),
        ("Last Name", "Ali Mohammed"),
        ("Email", "yakubali.mohammed@applywizard.ai"),
        ("Phone", "+1234567890"),
        ("LinkedIn", "https://www.linkedin.com/in/yakub-mohammed"),
    ]:
        try:
            page.get_by_label(re.compile(label, re.I)).fill(value, timeout=5000)
            results[label] = "fill() succeeded"
        except Exception as e:
            results[label] = f"fill() FAILED: {type(e).__name__}: {e}"

    # read back actual DOM values regardless of what fill() reported
    readback = page.evaluate("""
        () => ({
          first_name: document.getElementById('first_name')?.value,
          last_name: document.getElementById('last_name')?.value,
          email: document.getElementById('email')?.value,
          phone: document.getElementById('phone')?.value,
        })
    """)

    print("--- fill() call results ---")
    for k, v in results.items():
        print(f"{k}: {v}")
    print("--- actual DOM values after fill ---")
    print(readback)

    browser.close()
