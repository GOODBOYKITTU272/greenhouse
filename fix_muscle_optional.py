with open('applywizz_muscle.py', 'r') as f:
    text = f.read()

old_logic = """                # Skip empty/optional answers
                if not answer or matched_by == 'skipped_optional':
                    skipped.append(label)
                    continue"""

new_logic = """                # Skip empty/optional answers only if they genuinely have no answer string
                if not answer and matched_by == 'skipped_optional':
                    skipped.append(label)
                    continue"""

text = text.replace(old_logic, new_logic)

with open('applywizz_muscle.py', 'w') as f:
    f.write(text)
print("Muscle optional logic updated!")
