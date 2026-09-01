import re

with open('applywizz_muscle.py', 'r') as f:
    text = f.read()

# Replace the commented-out submit block with active code
old_block = """            # ┌─────────────────────────────────────────────────────┐
            # │ LIVE SUBMISSION DISABLED for testing                 │
            # │                                                     │
            # submit_btn = page.locator("button").filter(has_text="Submit Application").first
            # submit_btn.click(force=True)  # Might need force=True sometimes
            # submit_btn.click()
            # page.wait_for_timeout(8000)  # reCAPTCHA wait
            # log.info("✅ APPLICATION SUBMITTED!")
            # └─────────────────────────────────────────────────────┘"""

# Wait, let me check the exact text first to be safe, I might replace incorrectly.
