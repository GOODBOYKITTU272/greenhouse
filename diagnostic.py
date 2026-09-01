from playwright.sync_api import sync_playwright

def main():
    job_url = "https://job-boards.greenhouse.io/lendingtree/jobs/8155569?gh_src=zb723m9b1us"
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(job_url)
        page.wait_for_load_state("networkidle")
        
        print("--- INPUT ELEMENTS ---")
        inputs = page.locator("input").element_handles()
        for i in inputs[:15]:
            try:
                print(i.evaluate("el => el.outerHTML"))
            except:
                pass
        
        browser.close()

if __name__ == "__main__":
    main()
