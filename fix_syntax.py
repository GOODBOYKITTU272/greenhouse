with open('applywizz_brain.py', 'r') as f:
    text = f.read()

text = text.replace("                ai_count += 1\n                    ans = 'AI_PLACEHOLDER'", "                ai_count += 1")

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
