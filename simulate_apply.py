import requests
from bs4 import BeautifulSoup
import json
import urllib3

urllib3.disable_warnings()

# Yakub's JSON Profile
candidate_json = {
  "client": {
    "full_name": "Yakub Ali Mohammed",
    "company_email": "yakubali.mohammed@applywizard.ai",
    "visa_type": "Other", 
  },
  "additional_information": {
    "primary_phone": "+1234567890",
    "linked_in_url": "https://www.linkedin.com/in/yakub-mohammed",
    "github_url": None,
    "resume_url": "https://applywizz-prod.s3.us-east-2.amazonaws.com/CRM/AWL-30453.pdf"
  }
}

def determine_sponsorship(visa_type):
    visa = str(visa_type).upper()
    if visa in ['US CITIZEN', 'GREEN CARD', 'GC']: return "No"
    else: return "Yes"

# Load proxy
proxy_url = None
try:
    with open("proxies.txt", "r") as f:
        p = f.readline().strip()
        parts = p.split(':')
        proxy_url = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
except Exception:
    pass

session = requests.Session()
if proxy_url:
    session.proxies = {"http": proxy_url, "https": proxy_url}

print(f"--- SIMULATING FOR: {candidate_json['client']['full_name']} ---")

try:
    response = session.get("https://grnh.se/axttqm929us", allow_redirects=True, timeout=10, verify=False)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    token_input = soup.find('input', {'name': 'mapped_url_token'})
    if not token_input:
        print("ERROR: Not a standard Greenhouse board.")
    else:
        form_data = {
            "first_name": "Yakub",
            "last_name": "Ali Mohammed",
            "email": "yakubali.mohammed@applywizard.ai",
            "phone": "+1234567890",
            "urls[LinkedIn]": "https://www.linkedin.com/in/yakub-mohammed"
        }

        print("\n--- EXTRACTING DYNAMIC QUESTIONS FROM GREENHOUSE ---")
        for field in soup.find_all('div', class_='field'):
            label = field.find('label')
            if not label: continue
            label_text = label.text.strip().replace('\n', ' ').replace('  ', ' ')
            select_box = field.find('select')
            
            if select_box:
                question_name = select_box.get('name', 'unknown')
                print(f"\nFound Question: {label_text.split('*')[0].strip()}")
                
                if 'relocat' in label_text.lower():
                    print(" -> APPLYWIZZ RULE: Enforcing 'Yes' for Relocation")
                    form_data[question_name] = "Yes"
                elif 'sponsorship' in label_text.lower() or 'sponsor' in label_text.lower():
                    ans = determine_sponsorship(candidate_json['client']['visa_type'])
                    print(f" -> APPLYWIZZ RULE: Derived '{ans}' from Visa Type '{candidate_json['client']['visa_type']}'")
                    form_data[question_name] = ans
                elif 'authorized' in label_text.lower() or 'legally' in label_text.lower():
                    print(" -> APPLYWIZZ RULE: Automatically answering 'Yes' to authorization")
                    form_data[question_name] = "Yes"

        print("\n--- FINAL GENERATED PAYLOAD ---")
        print(json.dumps(form_data, indent=4))
        print("STATUS: SUCCESS. Ready to POST to Greenhouse server.")
except Exception as e:
    print("Failed to fetch:", e)
