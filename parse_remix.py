import requests
import json
import re

url = "https://job-boards.greenhouse.io/lendingtree/jobs/8155569?gh_src=zb723m9b1us"
r = requests.get(url)
match = re.search(r"window\.__remixContext = (.*?);</script>", r.text)
if match:
    data = json.loads(match.group(1))
    print(json.dumps(data, indent=2)[:1500])
else:
    print("No remix context found.")
