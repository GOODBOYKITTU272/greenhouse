with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# FIX 1: Salary - detect hourly vs annual and convert properly
old_salary = """        elif any(w in ll for w in ['salary', 'compensation', 'pay expectation', 'desired pay', 'hourly rate']):
            intent = c.get('salary_expectation', 'Open to discussion')"""

new_salary = """        elif any(w in ll for w in ['salary', 'compensation', 'pay expectation', 'desired pay', 'hourly rate', 'desired pay rate']):
            raw_salary = str(c.get('salary_expectation', 'Open to discussion'))
            import re as _re
            # If the question asks for HOURLY rate specifically
            if 'hourly' in ll:
                # Check if API has "Hourly: 40-60" format
                hourly_match = _re.search(r'[Hh]ourly[:\s]*([\d\-k]+)', raw_salary)
                if hourly_match:
                    intent = hourly_match.group(1)  # e.g. "40-60"
                elif raw_salary.replace(',','').isdigit():
                    # Convert annual to hourly: divide by 2080 working hours/year
                    annual = int(raw_salary.replace(',',''))
                    if annual > 500:
                        intent = str(round(annual / 2080))
                    else:
                        intent = raw_salary
                else:
                    intent = raw_salary
            else:
                # Annual salary question
                yearly_match = _re.search(r'[Yy]early[:\s]*([^\,]+)', raw_salary)
                if yearly_match:
                    intent = yearly_match.group(1).strip()
                else:
                    intent = raw_salary"""

text = text.replace(old_salary, new_salary)

# FIX 2: Multi-select checkbox questions should NOT go to ChatGPT
# They need to be reviewed by the human in the Dossier
# In process_questions, if field_type is multi_value_multi_select, mark as needs_human
old_ai_fallback = """            # --- STEP 3: AI Fallback ---
            if ans is None:
                if not required:
                    matched_by = 'skipped_optional'
                    ans = ''
                else:
                    matched_by = 'ai_fallback'
                    needs_ai = True
                    ai_count += 1
                    ans = 'AI_PLACEHOLDER'"""

new_ai_fallback = """            # --- STEP 3: AI Fallback ---
            if ans is None:
                if not required:
                    matched_by = 'skipped_optional'
                    ans = ''
                elif field_type in ['multi_value_multi_select', 'multi_value_multi_select_other']:
                    # Checkbox "select all that apply" — human must pick in Dossier
                    matched_by = 'needs_human_review'
                    ans = 'HUMAN_REVIEW_NEEDED'
                    needs_ai = False
                else:
                    matched_by = 'ai_fallback'
                    needs_ai = True
                    ai_count += 1
                    ans = 'AI_PLACEHOLDER'"""

text = text.replace(old_ai_fallback, new_ai_fallback)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Salary and checkbox fixes applied!")
