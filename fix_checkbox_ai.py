with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# REVERT the human_review approach for checkboxes
# Instead, pass checkbox options to ChatGPT so it can pick the right ones

old_checkbox = """                elif field_type in ['multi_value_multi_select', 'multi_value_multi_select_other']:
                    # Checkbox "select all that apply" — human must pick in Dossier
                    matched_by = 'needs_human_review'
                    ans = 'HUMAN_REVIEW_NEEDED'
                    needs_ai = False
                else:"""

new_checkbox = """                elif field_type in ['multi_value_multi_select', 'multi_value_multi_select_other']:
                    # Checkbox: send to AI with the full options list so it can pick correctly
                    matched_by = 'ai_fallback'
                    needs_ai = True
                    ai_count += 1
                    ans = 'AI_PLACEHOLDER'
                else:"""

text = text.replace(old_checkbox, new_checkbox)

# Now fix resolve_ai_questions to include available options for checkbox questions
# so ChatGPT can select from the real list, not guess

old_questions_build = """        questions_text = ""
        for i, q in enumerate(remaining):
            questions_text += f"{i}. {q['question_label']}\\n" """

new_questions_build = """        questions_text = ""
        for i, q in enumerate(remaining):
            label = q['question_label']
            opts = q.get('options_for_ai', [])
            if opts:
                opts_str = ", ".join([str(o) for o in opts[:20]])
                questions_text += f"{i}. {label}\\n   Available options (select only what applies): {opts_str}\\n"
            else:
                questions_text += f"{i}. {label}\\n" """

text = text.replace(old_questions_build, new_questions_build)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Checkbox AI fix applied!")
