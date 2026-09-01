with open('applywizz_brain.py', 'r') as f:
    text = f.read()

text = text.replace(
    "questions = job_data.get('questions', [])",
    "questions = job_data.get('questions') or []"
).replace(
    "demo_questions = job_data.get('demographic_questions', {}).get('questions', [])",
    "demo_questions = (job_data.get('demographic_questions') or {}).get('questions') or []"
).replace(
    "demo_questions = job_data.get('compliance', [])[0].get('questions', [])",
    "try:\\n            demo_questions = (job_data.get('compliance') or [])[0].get('questions') or []\\n        except:\\n            demo_questions = []"
)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
