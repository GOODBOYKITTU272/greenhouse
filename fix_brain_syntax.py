with open('applywizz_brain.py', 'r') as f:
    text = f.read()

text = text.replace(
    '''"- For URL/Link fields, output an empty string '' instead of 'N/A' if missing.\\n- If asked if authorized to lawfully work, ALWAYS answer 'Yes'.\\n- If asked for a preferred name, output the candidate's actual name, NOT 'Yes'.\\n- If the question asks for a signature and date, output the candidate's full legal name followed by today's date (e.g., 'Srujan Maryala {datetime.datetime.now().strftime("%m/%d/%y")}').\\n"''',
    '''f"- For URL/Link fields, output an empty string '' instead of 'N/A' if missing.\\n- If asked if authorized to lawfully work, ALWAYS answer 'Yes'.\\n- If asked for a preferred name, output the candidate's actual name, NOT 'Yes'.\\n- If the question asks for a signature and date, output the candidate's full legal name followed by today's date (e.g., 'Srujan Maryala {datetime.datetime.now().strftime('%m/%d/%y')}').\\n"'''
)

with open('applywizz_brain.py', 'w') as f:
    f.write(text)
