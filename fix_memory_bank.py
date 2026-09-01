with open('applywizz_brain.py', 'r') as f:
    text = f.read()

text = text.replace(
    'def __init__(self, job_url, candidate_profile):',
    'def __init__(self, job_url, candidate_profile, memory_bank=None):'
)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
