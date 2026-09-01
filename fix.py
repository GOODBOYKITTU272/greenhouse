with open('applywizz_brain.py', 'r') as f:
    content = f.read()

bad_str1 = 'text += page.extract_text() + "\n"'
good_str1 = 'text += page.extract_text() + "\\n"'
content = content.replace(bad_str1, good_str1)

bad_str2 = 'questions_prompt = "Questions to answer:\n"'
good_str2 = 'questions_prompt = "Questions to answer:\\n"'
content = content.replace(bad_str2, good_str2)

bad_str3 = 'questions_prompt += f"{i}. {q[\'question_label\']}{options}\n"'
good_str3 = 'questions_prompt += f"{i}. {q[\'question_label\']}{options}\\n"'
content = content.replace(bad_str3, good_str3)

bad_str4 = 'results, total_ai_count = self.process_questions(all_fields)'
good_str4 = '        results, total_ai_count = self.process_questions(all_fields)'
content = content.replace(bad_str4, good_str4)

import re
# Fix the big prompt
content = re.sub(r'prompt = f"You are an expert.*?\n\nResume:\n{resume_text}\n\n{questions_prompt}\n\n.*?"',
                 r'prompt = f"You are an expert job applicant. Answer these application questions accurately based ONLY on the provided resume. Keep answers professional, extremely concise (under 2 sentences), and do not use placeholders.\\n\\nResume:\\n{resume_text}\\n\\n{questions_prompt}\\n\\nReturn ONLY a valid JSON array of strings, where each string is the answer to the question in the exact same order. Example: [\\"Yes, I am willing to work onsite.\\", \\"I have 2 years of forecasting experience.\\"]"',
                 content, flags=re.DOTALL)

with open('applywizz_brain.py', 'w') as f:
    f.write(content)
