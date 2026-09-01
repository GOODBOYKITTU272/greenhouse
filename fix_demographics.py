with open('applywizz_brain.py', 'r') as f:
    text = f.read()

new_demo = """        # Safely extract demographic questions
        demo_obj = job_data.get('demographic_questions')
        demo_questions = []
        if isinstance(demo_obj, dict):
            demo_questions = demo_obj.get('questions', [])
        elif isinstance(demo_obj, list):
            demo_questions = demo_obj

        # Safely extract compliance questions
        comp_obj = job_data.get('compliance')
        if isinstance(comp_obj, list):
            for c in comp_obj:
                if isinstance(c, dict):
                    demo_questions.extend(c.get('questions', []))"""

import re
text = re.sub(r'        demo_questions = job_data\.get\(\'demographic_questions\'.*?\[\]\)', new_demo, text, flags=re.DOTALL)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
