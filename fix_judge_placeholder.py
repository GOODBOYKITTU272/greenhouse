with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# Fix Judge LLM prompt to ban AI_PLACEHOLDER
old_rule = "- If answer is 'AI_PLACEHOLDER' or blank for a required field, write the best possible answer. HOWEVER, if it is a URL field (like LinkedIn or Website) and the candidate has none, leave it as an empty string ''."
new_rule = "- If answer is 'AI_PLACEHOLDER' or blank, write the best possible answer based on the candidate data. NEVER output the word 'AI_PLACEHOLDER' yourself. If the question is truly unanswerable or empty (like an Address Line 2, or a legal signature you don't have), leave it as an empty string '' or 'N/A', but absolutely NEVER type 'AI_PLACEHOLDER'."

text = text.replace(old_rule, new_rule)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Banned Judge LLM from writing AI_PLACEHOLDER!")
