with open('applywizz_brain.py', 'r') as f:
    text = f.read()

import re
# We want to replace from 'try:' on line 358 down to line 410 with the correct clean block.
correct = """
            try:
                response = client.chat.completions.create(
                    model="openai/gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.1
                )
                answer = response.choices[0].message.content.strip()

                # ZERO-TOUCH BUSINESS FILTERS
                ll = label.lower()
                
                # 1. Address Line 2 & 3 must always be blank
                if 'address line 2' in ll or 'address line 3' in ll or 'county' in ll:
                    answer = ""
                    
                # 2. Cover Letter Name Bug
                if 'cover letter' in ll:
                    if len(answer) < 50 or 'srujan' in answer.lower():
                        answer = ""
                        
                # Force Race to Asian
                if 'race' in ll or 'racial' in ll or 'ethnic' in ll:
                    answer = "Asian"
                    
                # 3. Signature Lie Detector
                if 'signature' in ll or 'lie detector' in ll:
                    answer = f"{candidate.get('first_name','')} {candidate.get('last_name','')}"
                    
                # 4. Hallucinated AWS Link Bug
                if 'amazonaws.com' in answer.lower() and 'resume' not in ll and 'cv' not in ll:
                    answer = ""
                    
                # Clean up quotes
                if answer.startswith('"') and answer.endswith('"'):
                    answer = answer[1:-1]
                if answer.startswith("'") and answer.endswith("'"):
                    answer = answer[1:-1]

                q['answer'] = answer
                q['needs_ai'] = False
                print(f"  AI (1-by-1): {q['question_label'][:40]} -> {q['answer']}")
                
            except Exception as e:
                print(f"  AI Request failed for question '{q.get('question_label', '')}': {e}")
                q['answer'] = ""
"""

# Just find the indices and replace
lines = text.split('\\n')
start = -1
end = -1
for i, l in enumerate(lines):
    if l.strip() == "try:" and "response = client.chat.completions.create(" in lines[i+1]:
        start = i
    if l.strip() == "# Final Check: Are all required questions answered?":
        end = i
        
if start != -1 and end != -1:
    new_text = '\\n'.join(lines[:start]) + correct + '\\n    # Final Check: Are all required questions answered?\\n' + '\\n'.join(lines[end+1:])
    with open('applywizz_brain.py', 'w') as f:
        f.write(new_text)
    print("Replaced successfully!")
else:
    print("Could not find blocks", start, end)
