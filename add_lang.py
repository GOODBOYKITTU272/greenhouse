with open('applywizz_brain.py', 'r') as f:
    text = f.read()

text = text.replace("k: v for k, v in self.candidate.items()", "k: v for k, v in {**self.candidate, 'languages': 'English, Hindi, Telugu'}.items()")

with open('applywizz_brain.py', 'w') as f:
    f.write(text)

