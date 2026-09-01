with open('applywizz_brain.py', 'r') as f:
    text = f.read()

import re

# Find the ChatGPT rule block
old_rule = "- If the question asks for a signature and date, output the candidate's full legal name followed by today's date (e.g., 'Srujan Maryala"
# We just replace the entire line containing "Srujan Maryala" inside the rules block
text = re.sub(
    r"- If the question asks for a signature and date, output the candidate's full legal name followed by today's date \(e\.g\., 'Srujan Maryala.*?\)\.\\n",
    r"- If the question asks for a signature and date, output the candidate's full legal name followed by today's date (e.g., 'Srujan Maryala {datetime.datetime.now().strftime(\"%m/%d/%y\")}').\\n",
    text
)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
