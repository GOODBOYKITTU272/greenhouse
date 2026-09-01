with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# Fix the basic_catch logic so it doesn't skip empty optional fields
# but sends them to AI instead

old_logic = """            if ans is not None:
                if ans == '' and not required:
                    matched_by = 'skipped_optional'
                elif ans == '' and required:
                    ans = None
                else:
                    matched_by = 'basic_catch'"""

new_logic = """            if ans is not None:
                if ans == '':
                    ans = None  # Send to AI fallback
                else:
                    matched_by = 'basic_catch'"""

text = text.replace(old_logic, new_logic)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
print("Basic catch optional logic removed!")
