with open('applywizz_brain.py', 'r') as f:
    text = f.read()

text = text.replace(
    'def __init__(self, job_url, candidate_profile, memory_bank=None):',
    'def __init__(self, job_url, candidate_profile, memory_bank=None, resume_text=None):\\n        self.resume_text = resume_text or ""'
)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
