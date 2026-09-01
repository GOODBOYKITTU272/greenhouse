with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# 1. Update resolve_ai_questions prompt
old_ai_prompt = "Example for 3 questions: [\"Excel, SQL\", \"Yes\", \"2 years of Python experience\"]"
new_ai_prompt = """Example for 3 questions: ["Excel, SQL", "Yes", "2 years of Python experience"]

IMPORTANT LOCATION RULE: If the question asks for a location, ONLY pick US-based locations since the candidate lives in the US. Do NOT pick UK or international options unless the candidate lives there.
IMPORTANT NAME/SIGNATURE RULE: If the question is a legal disclaimer asking for a signature (e.g. "Signature and Date", "Print Name"), output the candidate's full name ("Srujan Maryala")."""

text = text.replace(old_ai_prompt, new_ai_prompt)

# 2. LinkedIn Profile is an input URL, ensure it maps correctly if it's "linkedin" or "linkedin_url"
# The candidate object might have it under a different key.
# Actually, the user complained it was N/A for LinkedIn. In test candidate it's '', but maybe in real DB it's empty too? We can't fix their DB data, but we can ensure the prompt knows how to handle empty LinkedIn (leave blank).
# If the AI sees empty linkedin, it outputs 'N/A', but we want it to output '' so it doesn't type 'N/A' into a URL field.
old_na = "- If truly unknown: say 'N/A'. Do NOT skip any question. Do NOT merge answers.\\n\\n"
new_na = "- If truly unknown or missing (like a LinkedIn profile you don't have): say 'N/A', EXCEPT for URL/Link fields where you MUST output an empty string '' instead of 'N/A'.\\n\\n"
text = text.replace(old_na, new_na)

# 3. Fix Judge LLM prompt for locations and signatures
old_judge_rules = "- For checkbox answers (comma-separated), keep only options confirmed in the candidate data.\\n"
new_judge_rules = """- For checkbox answers (comma-separated), keep only options confirmed in the candidate data.\\n- If the question is a location preference, strictly ensure it is US-based (if the candidate is in the US). Do NOT allow foreign countries.\\n- If it's a signature block, ensure the answer is the candidate's name, not 'AI_PLACEHOLDER'.\\n"""
text = text.replace(old_judge_rules, old_judge_rules + new_judge_rules)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Prompts updated!")
