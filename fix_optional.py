with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# Make the AI answer ALL questions, even optional ones
# Change the fallback logic

old_logic = """            if ans is None:
                if not required:
                    matched_by = 'skipped_optional'
                    ans = ''
                elif field_type in ['multi_value_multi_select', 'multi_value_multi_select_other']:"""

new_logic = """            if ans is None:
                if field_type in ['multi_value_multi_select', 'multi_value_multi_select_other']:"""

text = text.replace(old_logic, new_logic)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Optional field logic removed!")
