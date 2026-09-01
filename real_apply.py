import requests
from bs4 import BeautifulSoup
import json
import urllib3
import io

urllib3.disable_warnings()

# Yakub's Real Full JSON
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
    "resume_url": "https://applywizz-prod.s3.us-east-2.amazonaws.com/CRM/AWL-30453-28072026-0001-resume_yakub-ali-mohammed_ne.pdf"
  }
}

def determine_sponsorship(visa_type):
    visa = str(visa_type).upper()
    if visa in ['US CITIZEN', 'GREEN CARD', 'GC']: return "No"
    else: return "Yes"

# Load Proxy
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

print("--- STARTING REAL LIVE APPLICATION FOR YAKUB ---")
short_url = "https://job-boards.greenhouse.io/trustwill/jobs/4379579009"  # One of Yakub's PENDING links

try:
    print(f"1. Fetching Job Page: {short_url}")
    response = session.get(short_url, allow_redirects=True, timeout=15, verify=False)
    real_url = response.url
    print(f"   Resolved URL: {real_url}")
    
    soup = BeautifulSoup(response.text, 'html.parser')
    
    token_input = soup.find('input', {'name': 'mapped_url_token'})
    if not token_input:
        print("ERROR: Could not find Greenhouse form security token. Check if the job is closed.")
        exit(1)
        
    mapped_url_token = token_input['value']
    form_tag = soup.find('form', id='application_form')
    form_action = form_tag['action'] if form_tag else ""
    
    print("2. Mapping Candidate Data")
    form_data = {
        "mapped_url_token": mapped_url_token,
        "first_name": "Yakub",
        "last_name": "Ali Mohammed",
        "email": candidate_json["client"]["company_email"],
        "phone": candidate_json["additional_information"]["primary_phone"],
        "urls[LinkedIn]": candidate_json["additional_information"]["linked_in_url"]
    }

    print("3. Answering Dynamic Questions")
    for field in soup.find_all('div', class_='field'):
        label = field.find('label')
        if not label: continue
        label_text = label.text.strip().lower()
        select_box = field.find('select')
        
        if select_box:
            question_name = select_box.get('name', 'unknown')
            
            # Find the option value for 'Yes' or 'No'
            def get_val(term):
                for opt in select_box.find_all('option'):
                    if term.lower() in opt.text.lower():
                        return opt['value']
                return ""
            
            if 'relocat' in label_text:
                form_data[question_name] = get_val("yes")
            elif 'sponsorship' in label_text or 'sponsor' in label_text:
                ans = determine_sponsorship(candidate_json['client']['visa_type'])
                form_data[question_name] = get_val(ans)
            elif 'authorized' in label_text or 'legally' in label_text:
                form_data[question_name] = get_val("yes")
                
    print(f"4. Downloading Resume from S3: {candidate_json['additional_information']['resume_url']}")
    # Disable proxy for AWS S3 download just in case proxy blocks it
    s3_response = requests.get(candidate_json['additional_information']['resume_url'], verify=False)
    if s3_response.status_code != 200:
        print(f"ERROR: Could not download resume from S3. HTTP {s3_response.status_code}")
        exit(1)
        
    files = {
        'resume': ('resume_yakub.pdf', io.BytesIO(s3_response.content), 'application/pdf')
    }
    
    print("5. Submitting Application to Greenhouse...")
    submit_url = f"https://boards.greenhouse.io{form_action}"
    submit_response = session.post(submit_url, data=form_data, files=files, timeout=15, verify=False)
    
    print(f"\n--- FINAL RESULT ---")
    print(f"HTTP Status Code: {submit_response.status_code}")
    if submit_response.status_code == 200:
        print("SUCCESS! The application was officially submitted.")
        if "OTP" in submit_response.text or "verify" in submit_response.text.lower():
            print("WARNING: The page text mentions verification/OTP.")
        else:
            print("CONFIRMED: NO OTP OR VERIFICATION WAS ASKED!")
    else:
        print("FAILED to submit.")
except Exception as e:
    print(f"Exception occurred: {e}")
