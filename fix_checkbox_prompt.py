with open('applywizz_brain.py', 'r') as f:
    text = f.read()

old_prompt_instruction = '''        prompt = (
            "You are filling out a job application. Answer EVERY question below. "
            f"There are exactly {len(remaining)} questions. Your response MUST be a JSON array with exactly {len(remaining)} strings. "
            "Answer truthfully and concisely (1-2 sentences max) based on the candidate data and resume. "
            "If the answer is not in the data, say 'N/A'. Do NOT skip any question. Do NOT merge answers.\\n\\n"
            f"CANDIDATE DATA:\\n{candidate_summary}\\n\\n"
            f"RESUME TEXT:\\n{self.resume_text[:3000]}\\n\\n"
            f"QUESTIONS TO ANSWER (answer ALL {len(remaining)} in order):\\n{questions_text}\\n"
            f"Return a JSON array of exactly {len(remaining)} strings. "
            "Example for 3 questions: [\\"answer1\\", \\"answer2\\", \\"answer3\\"]"
        )'''

new_prompt_instruction = '''        prompt = (
            "You are filling out a job application. Answer EVERY question below. "
            f"There are exactly {len(remaining)} questions. Your response MUST be a JSON array with exactly {len(remaining)} strings. "
            "Rules:\\n"
            "- Answer truthfully based ONLY on candidate data and resume. Do NOT invent experience.\\n"
            "- For questions with 'Available options': pick ONLY options that are confirmed in the candidate data/resume. Return them as a comma-separated string e.g. 'Excel, SQL'. If none apply, return 'None'.\\n"
            "- For yes/no questions without options: answer 'Yes' or 'No'.\\n"
            "- For open text questions: answer concisely in 1-2 sentences.\\n"
            "- If truly unknown: say 'N/A'. Do NOT skip any question. Do NOT merge answers.\\n\\n"
            f"CANDIDATE DATA:\\n{candidate_summary}\\n\\n"
            f"RESUME TEXT:\\n{self.resume_text[:3000]}\\n\\n"
            f"QUESTIONS TO ANSWER (answer ALL {len(remaining)} in order):\\n{questions_text}\\n"
            f"Return a JSON array of exactly {len(remaining)} strings. "
            "Example for 3 questions: [\\"Excel, SQL\\", \\"Yes\\", \\"2 years of Python experience\\"]"
        )'''

text = text.replace(old_prompt_instruction, new_prompt_instruction)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Prompt updated!")
