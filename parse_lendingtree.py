import requests
import json
import re

url = "https://job-boards.greenhouse.io/lendingtree/jobs/8155569?gh_src=zb723m9b1us"
response = requests.get(url)

# The new Remix apps embed the job data in window.__remixContext
match = re.search(r'window\.__remixContext = (.*?);</script>', response.text, re.DOTALL)
if match:
    data = json.loads(match.group(1))
    
    # Try to find the job post data in the nested Remix state
    try:
        # Search for questions in the state
        state = data.get('state', {})
        loader_data = state.get('loaderData', {})
        for key, val in loader_data.items():
            if 'jobPost' in val:
                questions = val['jobPost'].get('questions', [])
                print(f"Found {len(questions)} custom questions!")
                for q in questions:
                    required = " (REQUIRED)" if q.get("required") else ""
                    print(f"- {q.get('name')}{required}")
                    for opt in q.get('answers', []):
                        if isinstance(opt, dict) and 'name' in opt:
                            print(f"    * {opt['name']}")
    except Exception as e:
        print("Error parsing state:", e)
else:
    print("Could not find Remix context.")
