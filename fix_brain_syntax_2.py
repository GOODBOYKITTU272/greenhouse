import re

with open('applywizz_brain.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "ZERO-TOUCH BUSINESS FILTERS" in line:
        # We will rewrite the zero touch block correctly below
        break
    new_lines.append(line)

# Let's cleanly inject the Zero-Touch block and the rest of the try-except
correct_block = """
                answer = response.choices[0].message.content.strip()
            except Exception as e:
                print(f"  AI Request failed for question '{q.get('question_label', '')}': {e}")
                answer = ""

            # ZERO-TOUCH BUSINESS FILTERS
            ll = label.lower()
            
            # 1. Address Line 2 & 3 must always be blank
            if 'address line 2' in ll or 'address line 3' in ll or 'county' in ll:
                answer = ""
                
            # 2. Cover Letter Name Bug (If the AI just output the candidate's name, wipe it)
            if 'cover letter' in ll:
                if len(answer) < 50 or 'srujan' in answer.lower():
                    answer = ""
                    
            # Force Race to Asian
            if 'race' in ll or 'racial' in ll or 'ethnic' in ll:
                answer = "Asian"
                
            # 3. Signature Lie Detector forced to Name + Date
            if 'signature' in ll or 'lie detector' in ll:
                answer = f"{candidate.get('first_name','')} {candidate.get('last_name','')}"
                
            # 4. Hallucinated AWS Link Bug
            if 'amazonaws.com' in answer.lower() and 'resume' not in ll and 'cv' not in ll:
                answer = ""
                
            # Clean up quotes if ChatGPT wrapped the answer in them
            if answer.startswith('"') and answer.endswith('"'):
                answer = answer[1:-1]
            if answer.startswith("'") and answer.endswith("'"):
                answer = answer[1:-1]

            q['answer'] = answer
            q['needs_ai'] = False
            print(f"  AI (1-by-1): {q['question_label'][:40]} -> {q['answer']}")
            
        except Exception as e:
            print(f"  Failed for question '{q.get('question_label', '')}': {e}")

    # Final Check: Are all required questions answered?
    ai_questions_count = len([q for q in answer_map if q.get('needs_ai') is True])
    
    # Save the output
    output = {
        'job_url': job_url,
        'board_token': board_token,
        'job_id': job_id,
        'job_title': job_title,
        'status': 'needs_review',
        'ai_questions_count': ai_questions_count,
        'answer_map': answer_map
    }
    
    print(f"\\n✅ Extracted {len(answer_map)} questions for {job_title}")
    return output

if __name__ == "__main__":
    pass
"""

with open('applywizz_brain.py', 'w') as f:
    f.writelines(new_lines)
    f.write(correct_block)

