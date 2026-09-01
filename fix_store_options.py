with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# When appending the result, store options for AI questions
old_append = """            results.append({
                "question_label": label,
                "field_name": field_name,
                "field_type": field_type,
                "required": required,
                "answer": ans,
                "matched_by": matched_by,
                "needs_ai": needs_ai
            })"""

new_append = """            result_entry = {
                "question_label": label,
                "field_name": field_name,
                "field_type": field_type,
                "required": required,
                "answer": ans,
                "matched_by": matched_by,
                "needs_ai": needs_ai
            }
            # For AI fallback questions that have options (dropdowns/checkboxes),
            # store the option labels so ChatGPT can choose from the real list
            if needs_ai and options:
                result_entry["options_for_ai"] = [o.get('label', str(o)) for o in options]
            results.append(result_entry)"""

text = text.replace(old_append, new_append)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Options storage fix applied!")
