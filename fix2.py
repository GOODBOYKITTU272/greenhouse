with open('applywizz_brain.py', 'r') as f:
    text = f.read()

text = text.replace('def extract_resume_text(self):', '    def extract_resume_text(self):')

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
