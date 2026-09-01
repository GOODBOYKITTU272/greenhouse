import requests
import json

url = "https://boards-api.greenhouse.io/v1/boards/lendingtree/jobs/8155569?questions=true"
headers = {"User-Agent": "Mozilla/5.0"}
data = requests.get(url, headers=headers).json()

if "demographic_questions" in data:
    questions = data["demographic_questions"].get("questions", [])
    for q in questions:
        label = q.get("label", "").replace("\n", " ").strip()
        opts = []
        if "answer_options" in q:
            opts = [v.get("label") for v in q["answer_options"]]
        print(f"Question: {label}")
        print(f"Options: {opts}\n")
