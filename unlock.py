with open('applywizz_muscle.py', 'r') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if line.strip() == 'log.info("⚠️  SAFETY LOCK: Submit is disabled. Uncomment to enable.")':
        new_lines.append('            log.info("⚠️  SAFETY LOCK REMOVED: Submitting for real...")\n')
    elif line.strip() == '# submit_btn = page.locator("button").filter(has_text="Submit Application").first' or line.strip() == '# submit_btn = page.locator("button", has_text="Submit Application").first':
        new_lines.append('            submit_btn = page.locator("button:has-text(\'Submit Application\')").first\n')
    elif line.strip() == '# submit_btn.click()':
        new_lines.append('            submit_btn.click()\n')
    elif line.strip() == '# page.wait_for_timeout(8000)  # reCAPTCHA wait':
        new_lines.append('            page.wait_for_timeout(8000)  # wait for submit / captcha / redirect\n')
    elif line.strip() == '# log.info("✅ APPLICATION SUBMITTED!")':
        new_lines.append('            log.info("✅ APPLICATION SUBMITTED!")\n')
    else:
        new_lines.append(line)

with open('applywizz_muscle.py', 'w') as f:
    f.writelines(new_lines)
print("Safety lock removed!")
