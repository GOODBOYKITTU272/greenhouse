with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# FIX 1: VeteranStatus - pass the FULL API value so the matcher finds it
old_vet = """        elif any(w in ll for w in ['veteran', 'armed forces', 'served in the military', 'military service', 'military branch', 'military status']):
            vet = str(c.get('veteran', '')).lower()
            if 'not a protected' in vet or 'i am not' in vet:
                intent = 'No'
            elif vet and vet != 'decline':
                intent = c.get('veteran')
            else:
                intent = 'DECLINE'"""

new_vet = """        elif any(w in ll for w in ['veteran', 'armed forces', 'served in the military', 'military service', 'military branch', 'military status']):
            vet = str(c.get('veteran', ''))
            if vet and vet.lower() not in ['', 'none', 'decline']:
                intent = vet  # Pass the full value e.g. "I am not a protected veteran"
            else:
                intent = 'DECLINE'"""

text = text.replace(old_vet, new_vet)

# FIX 2: "If so" follow-up questions should always be skipped (they're conditional on a Yes)
# Add this logic at the START of process_questions loop, before basic_catch
old_process = """        ans = self.match_basic(field_name)
            matched_by = None
            needs_ai = False"""

new_process = """        # Auto-skip "If so, ..." follow-up questions — they only apply if the prior answer was Yes
            if label.lower().startswith('if so') or label.lower().startswith('if yes'):
                results.append({
                    "question_label": label,
                    "field_name": field_name,
                    "field_type": field_type,
                    "required": False,
                    "answer": "",
                    "matched_by": "skipped_conditional",
                    "needs_ai": False
                })
                continue

            ans = self.match_basic(field_name)
            matched_by = None
            needs_ai = False"""

text = text.replace(old_process, new_process)

# FIX 3: Stricter ChatGPT prompt with numbered format to prevent answer shifting
old_prompt = """        prompt = (
            "You are filling out a job application on behalf of a candidate. "
            "Answer each question truthfully and concisely (1-2 sentences max) based on the candidate data and resume below. "
            "Do NOT make up facts. If the answer is not in the data, say 'N/A'.\\n\\n"
            f"CANDIDATE DATA:\\n{candidate_summary}\\n\\n"
            f"RESUME TEXT:\\n{self.resume_text[:3000]}\\n\\n"
            f"QUESTIONS:\\n{questions_text}\\n"
            "Return ONLY a valid JSON array of strings in the same order as the questions. "
            'Example: ["Yes", "5 years of Python experience"]'
        )"""

new_prompt = """        prompt = (
            "You are filling out a job application. Answer EVERY question below. "
            f"There are exactly {len(remaining)} questions. Your response MUST be a JSON array with exactly {len(remaining)} strings. "
            "Answer truthfully and concisely (1-2 sentences max) based on the candidate data and resume. "
            "If the answer is not in the data, say 'N/A'. Do NOT skip any question. Do NOT merge answers.\\n\\n"
            f"CANDIDATE DATA:\\n{candidate_summary}\\n\\n"
            f"RESUME TEXT:\\n{self.resume_text[:3000]}\\n\\n"
            f"QUESTIONS TO ANSWER (answer ALL {len(remaining)} in order):\\n{questions_text}\\n"
            f"Return a JSON array of exactly {len(remaining)} strings. "
            "Example for 3 questions: [\\\"answer1\\\", \\\"answer2\\\", \\\"answer3\\\"]"
        )"""

text = text.replace(old_prompt, new_prompt)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("All 3 fixes applied!")
