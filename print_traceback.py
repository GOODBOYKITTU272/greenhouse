with open('brain_worker.py', 'r') as f:
    text = f.read()

text = text.replace(
    "error_msg = str(e)\\n            logging.error(f\\"Error on Job [{job_id}]: {error_msg}\\")",
    "import traceback\\n            error_msg = str(e)\\n            logging.error(f\\"Error on Job [{job_id}]: {error_msg}\\\\n{traceback.format_exc()}\\")"
)

with open('brain_worker.py', 'w') as f:
    f.write(text)
