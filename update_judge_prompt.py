with open('applywizz_brain.py', 'r') as f:
    text = f.read()

import re

# We need to replace the old prompt with the user's new prompt in the judge_all_answers function.
old_prompt_start = '        prompt = (\n            "Review each Q&A pair below.'
old_prompt_end = '            \'Example: {"0": "corrected answer", "3": "48", "7": "Excel, SQL"}\'\n        )'

new_prompt = """        prompt = (
            "Review each Question & Answer pair below using the candidate data provided.\\n\\n"
            "For each pair, return the FINAL ANSWER only after checking whether the existing answer is correct, complete, consistent with the candidate data, and appropriate for the question.\\n\\n"
            "Rules:\\n\\n"
            "1. If the existing answer is correct and appropriate, return it unchanged.\\n\\n"
            "2. Salary / compensation:\\n"
            "   * If the question asks for HOURLY pay and the answer appears to be an annual salary (>500), convert it to hourly by dividing by 2080.\\n"
            "   * If the question asks for ANNUAL pay and the answer appears to be hourly (<200), convert it to annual by multiplying by 2080.\\n"
            "   * Preserve the currency when known.\\n"
            "   * Do not invent a compensation figure when candidate data does not support one.\\n\\n"
            "3. Multiple-choice / dropdown questions:\\n"
            "   * If options are provided, the final answer MUST be one of the listed options.\\n"
            "   * If the existing answer is not an exact option, select the closest semantically correct option based on candidate data.\\n"
            "   * Do not create a new option.\\n\\n"
            "4. Checkbox / multi-select questions:\\n"
            "   * Return only options explicitly supported by candidate data.\\n"
            "   * Remove unsupported selections.\\n"
            "   * Use the exact option wording supplied by the application whenever possible.\\n\\n"
            "5. Location questions:\\n"
            "   * Respect the candidate's stated location and relocation preferences.\\n"
            "   * If the candidate is US-based and the question asks for preferred work locations, do not select foreign countries unless the candidate data explicitly permits them.\\n"
            "   * Never invent a location preference.\\n\\n"
            "6. Signature / certification fields:\\n"
            "   * If the field is asking for the candidate's typed signature or full legal name, use the candidate's full name.\\n"
            "   * Do not fabricate initials, dates, or legal attestations that are not supported.\\n\\n"
            "7. Missing or placeholder answers:\\n"
            "   * If the existing answer is 'AI_PLACEHOLDER' or blank, infer the best supported answer from candidate data.\\n"
            "   * NEVER output the text 'AI_PLACEHOLDER'.\\n"
            "   * If the answer cannot be reliably determined from candidate data, return an empty string '' or 'N/A' where appropriate.\\n"
            "   * Examples of fields that may legitimately remain empty include Address Line 2 and truly unknown optional fields.\\n\\n"
            "8. Work authorization / immigration:\\n"
            "   * Use only the candidate's explicit work authorization, visa, and sponsorship information.\\n"
            "   * Do not infer citizenship, permanent residency, visa category, OPT/STEM OPT status, or sponsorship eligibility unless explicitly present.\\n\\n"
            "9. Sensitive or legal questions:\\n"
            "   * Do not guess answers to criminal history, disability, veteran status, demographic, conflicts of interest, legal agreements, certifications, or other sensitive/legal questions.\\n"
            "   * Use only explicit candidate data.\\n"
            "   * If the information is unavailable, return '' or 'N/A' rather than inventing an answer.\\n\\n"
            "10. Experience and skill questions:\\n"
            "   * Do not claim skills, years of experience, certifications, employers, technologies, or accomplishments that are not supported by the resume or candidate data.\\n"
            "   * If an answer exaggerates the candidate's experience, correct it.\\n\\n"
            "11. Dates and numeric fields:\\n"
            "   * Ensure the answer matches the format requested by the question where possible.\\n"
            "   * Do not change a supported value merely to make it look more convenient.\\n\\n"
            "12. Consistency:\\n"
            "   * Resolve conflicts by prioritizing structured candidate data over previously generated answers.\\n"
            "   * Never contradict known candidate information.\\n"
            "   * Do not hallucinate missing facts.\\n\\n"
            "OUTPUT:\\n"
            "Return the corrected final answer for each Question & Answer pair. You MUST return a JSON object where keys are the question numbers (as strings) and values are the corrected answers.\\n"
            "Example: {\\\"0\\\": \\\"corrected answer\\\", \\\"3\\\": \\\"48\\\", \\\"7\\\": \\\"Excel, SQL\\\"}\\n\\n"
            f"CANDIDATE DATA:\\n{candidate_summary}\\n\\n"
            f"Q&A PAIRS TO REVIEW:\\n{review_text}"
        )"""

start_idx = text.find('        prompt = (\n            "Review each Q&A pair below.')
end_idx = text.find('        try:\n            client = OpenAI')

if start_idx != -1 and end_idx != -1:
    text = text[:start_idx] + new_prompt + "\n\n" + text[end_idx:]
    with open('applywizz_brain.py', 'w') as f:
        f.write(text)
    print("Judge LLM prompt successfully upgraded to the new enterprise version.")
else:
    print("Could not find the exact string to replace.")

