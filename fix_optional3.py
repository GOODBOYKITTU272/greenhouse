with open('applywizz_brain.py', 'r') as f:
    text = f.read()

old_logic = """            if ans is None:
                if not required:
                    matched_by = 'skipped_optional'
                    ans = ''
                else:
                    matched_by = 'ai_fallback'
                    needs_ai = True
                    ai_count += 1"""

new_logic = """            if ans is None:
                matched_by = 'ai_fallback'
                ans = 'AI_PLACEHOLDER'
                needs_ai = True
                ai_count += 1"""

text = text.replace(old_logic, new_logic)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Finally killed skipped_optional logic!")
