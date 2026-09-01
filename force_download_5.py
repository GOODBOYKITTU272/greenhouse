import requests, io
from supabase import create_client
try:
    from pypdf import PdfReader
except:
    PdfReader = None

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

ids = ['AWL-27275', 'AWL-33056', 'AWL-31630', 'AWL-24852', 'AWL-30475']

for aw_id in ids:
    print(f"Downloading {aw_id}...")
    try:
        url = f"https://www.apply-wizz.me/api/get-client-details?applywizz_id={aw_id}"
        r = requests.get(url, timeout=10)
        data = r.json()
        resume_url = data.get('additional_information', {}).get('resume_url')
        resume_text = ""
        if resume_url and PdfReader:
            pdf_resp = requests.get(resume_url, timeout=10)
            if pdf_resp.status_code == 200:
                reader = PdfReader(io.BytesIO(pdf_resp.content))
                for page in reader.pages:
                    resume_text += page.extract_text() + "\\n"
        
        # Check if exists
        check = db.table('candidate_profiles').select('applywizz_id').eq('applywizz_id', aw_id).execute()
        if not check.data:
            db.table('candidate_profiles').insert({
                'applywizz_id': aw_id,
                'profile_json': data,
                'resume_text': resume_text
            }).execute()
            print(f" -> Saved {aw_id} successfully!")
        else:
            print(f" -> {aw_id} already exists in DB!")
    except Exception as e:
        print(f" -> Failed {aw_id}: {e}")
