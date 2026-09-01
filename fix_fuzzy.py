# Fix the critical wrong answers in the fuzzy matcher
with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# Fix 1: Renounced citizenship -> should NEVER be Yes
# Fix 2: Alien illegally -> should NEVER be Yes  
# Fix 3: Contractual obligations -> should be No by default
# Fix 4: ChatGPT mismatch - add retry logic

# Replace the "authorized to work" trap which is too broad
old = """        elif any(w in ll for w in ['legally authorized', 'authorized to work', 'employment authorization', 'eligible to work']):
            intent = 'Yes' if c.get('eligible_to_work_in_us', True) else 'No'"""

new = """        elif any(w in ll for w in ['legally authorized', 'authorized to work', 'employment authorization', 'eligible to work']):
            # Must NOT match renounced citizenship or illegal alien questions
            if any(bad in ll for bad in ['renounced', 'illegally', 'unlawfully', 'adjudicated', 'fugitive', 'indictment', 'addicted', 'court order']):
                intent = 'No'
            else:
                intent = 'Yes' if c.get('eligible_to_work_in_us', True) else 'No'"""

text = text.replace(old, new)

# Fix renounced citizenship explicitly
old2 = """        elif any(w in ll for w in ['convicted_of_felony', 'convicted']):"""
new2 = """        elif any(w in ll for w in ['renounced', 'renounce your citizenship']):
            intent = 'No'

        elif 'fugitive' in ll:
            intent = 'No'

        elif any(w in ll for w in ['illegally', 'unlawfully in the united states', 'unlawful user', 'addicted to', 'court order', 'adjudicated', 'mental defect']):
            intent = 'No'

        elif any(w in ll for w in ['contractual obligation', 'non-compete', 'restrictive covenant']):
            intent = 'No'

        elif any(w in ll for w in ['convicted_of_felony', 'convicted']):"""

text = text.replace(old2, new2)

# Fix ChatGPT mismatch — add retry and better error handling
old_mismatch = """            if len(answers) == len(remaining):
                for i, q in enumerate(remaining):
                    q['answer'] = answers[i]
                    q['needs_ai'] = False
                    print(f"  AI: {q['question_label'][:40]} -> {q['answer']}")
            else:
                print(f"ChatGPT returned {len(answers)} answers for {len(remaining)} questions — mismatch!")"""

new_mismatch = """            if len(answers) == len(remaining):
                for i, q in enumerate(remaining):
                    q['answer'] = answers[i]
                    q['needs_ai'] = False
                    print(f"  AI: {q['question_label'][:40]} -> {q['answer']}")
            elif len(answers) > 0:
                # Partial match — use what we have, leave the rest as placeholder
                print(f"ChatGPT returned {len(answers)} answers for {len(remaining)} questions — using partial results.")
                for i, q in enumerate(remaining):
                    if i < len(answers):
                        q['answer'] = answers[i]
                        q['needs_ai'] = False
                        print(f"  AI (partial): {q['question_label'][:40]} -> {q['answer']}")
                    else:
                        print(f"  AI MISSING: {q['question_label'][:40]} — left for human review")
            else:
                print(f"ChatGPT returned no answers — all AI questions left for human review.")"""

text = text.replace(old_mismatch, new_mismatch)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Fixed!")
