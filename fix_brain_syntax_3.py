with open('applywizz_brain.py', 'r') as f:
    lines = f.readlines()

new_lines = []
skip = False
for i, line in enumerate(lines):
    if "try:" in line and "response = client.chat.completions.create(" in lines[i+1]:
        skip = True
        
    if skip and "except Exception as e:" in line and "Failed for question" in lines[i+1]:
        skip = False
        continue # Skip the except block lines too
        
    if not skip:
        new_lines.append(line)
