import csv
import requests
import io
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from supabase import create_client
try:
    from pypdf import PdfReader
except:
    PdfReader = None

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

def process_client(aw_id):
    try:
        url = f"https://www.apply-wizz.me/api/get-client-details?applywizz_id={aw_id}"
        r = requests.get(url, timeout=10)
        if r.status_code != 200: return False
        
        data = r.json()
        if 'client' not in data: return False
        
        resume_url = data.get('additional_information', {}).get('resume_url')
        resume_text = ""
        if resume_url and PdfReader:
            try:
                pdf_resp = requests.get(resume_url, timeout=10)
                if pdf_resp.status_code == 200:
                    reader = PdfReader(io.BytesIO(pdf_resp.content))
                    for page in reader.pages:
                        resume_text += page.extract_text() + "\\n"
            except:
                pass
                
        db.table('candidate_profiles').insert({
            'applywizz_id': aw_id,
            'profile_json': data,
            'resume_text': resume_text
        }).execute()
        return True
    except Exception as e:
        return False

missing = []
with open('/Users/ramakrishnachanda/Desktop/greenhosue/missing_resumes.csv', 'r') as f:
    for row in csv.DictReader(f):
        missing.append(row['ApplyWizz ID'])

print(f"Starting highly concurrent download of {len(missing)} profiles...")

success = 0
with ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(process_client, aw_id): aw_id for aw_id in missing}
    for i, future in enumerate(as_completed(futures), 1):
        if future.result():
            success += 1
        if i % 20 == 0:
            print(f"Progress: {i}/{len(missing)}... (Success: {success})")

print(f"Finished! Successfully batch downloaded {success} missing profiles into the database!")
