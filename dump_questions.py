import requests

url = "https://boards-api.greenhouse.io/v1/boards/lendingtree/jobs/8155569?questions=true"
headers = {"User-Agent": "Mozilla/5.0"}
data = requests.get(url, headers=headers).json()

all_questions = data.get("questions", [])
for eeoc in (data.get("compliance") or []):
    all_questions.extend(eeoc.get("questions", []))
if "demographic_questions" in data:
    all_questions.extend(data["demographic_questions"].get("questions", []))

for i, q in enumerate(all_questions, 1):
    label = q.get("label", "").replace("\n", " ").strip()
    print(f"{i}. {label}")
    fields = q.get("fields", [])
    if fields:
        field = fields[0]
        if "values" in field:
            opts = [v.get("label") for v in field["values"]]
            print(f"   Dropdown Options: {opts}")
        elif "answer_options" in field:
            opts = [v.get("label") for v in field["answer_options"]]
            print(f"   Dropdown Options: {opts}")
