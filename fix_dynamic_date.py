with open('applywizz_brain.py', 'r') as f:
    text = f.read()

# Make it dynamic in the code itself, not hardcoded during the patch
import re

# 1. Add datetime import at the top of the file if not exists
if "import datetime" not in text:
    text = "import datetime\n" + text

# 2. Fix the ChatGPT pass 1 prompt
# Find where the hardcoded date might be and replace it with dynamic f-string formatting
text = re.sub(
    r"- If the question asks for a signature and date, output the candidate's full legal name followed by today's date \(e\.g\., 'Srujan Maryala \d{2}/\d{2}/\d{2}'\)\.",
    r"- If the question asks for a signature and date, output the candidate's full legal name followed by today's date (e.g., 'Srujan Maryala {datetime.datetime.now().strftime(\"%m/%d/%y\")}')",
    text
)

# 3. Fix the Judge LLM prompt
text = re.sub(
    r"\* If the field is asking for the candidate's typed signature or full legal name, use the candidate's full name\. If it asks for Signature AND Date, output the name AND today's date \(e\.g\., Srujan Maryala \d{2}/\d{2}/\d{2}\)\.",
    r"* If the field is asking for the candidate's typed signature or full legal name, use the candidate's full name. If it asks for Signature AND Date, output the name AND today's date (e.g., Srujan Maryala {datetime.datetime.now().strftime(\"%m/%d/%y\")}).",
    text
)

# Make sure the prompts themselves evaluate the f-string at runtime
# (Since the prompt is already an f-string in applywizz_brain.py, injecting {datetime.datetime.now().strftime(...)} directly into the source code string will make Python evaluate it dynamically every time the function runs).

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
