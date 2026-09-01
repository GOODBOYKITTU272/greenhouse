with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# Fix Judge LLM prompt
old_judge_rules = "- If answer is 'AI_PLACEHOLDER' or blank for a required field, write the best possible answer."
new_judge_rules = "- If answer is 'AI_PLACEHOLDER' or blank for a required field, write the best possible answer. HOWEVER, if it is a URL field (like LinkedIn or Website) and the candidate has none, leave it as an empty string ''."

text = text.replace(old_judge_rules, new_judge_rules)

# Fix ChatGPT prompt to just output empty string instead of N/A for urls
old_na = "- If truly unknown or missing (like a LinkedIn profile you don't have): say 'N/A', EXCEPT for URL/Link fields where you MUST output an empty string '' instead of 'N/A'.\\n\\n"
new_na = "- If truly unknown or missing: say 'N/A'. However, for Website or LinkedIn Profile, output an empty string ''.\\n\\n"

text = text.replace(old_na, new_na)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Judge LLM logic fixed for URLs!")
