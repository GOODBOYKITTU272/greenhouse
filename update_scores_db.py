import csv
from supabase import create_client

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

# 1. Load scores from CSV into a dictionary keyed by URL + Client Name (to be safe)
csv_scores = {}
print("Reading CSV...")
with open("/Users/ramakrishnachanda/Desktop/greenhosue/Greenhouse 1.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        url = row.get('url', '').strip()
        client = row.get('Client Name', '').strip()
        score = row.get('score', '0')
        csv_scores[f"{client}|{url}"] = score

# 2. Update Supabase
print(f"Loaded {len(csv_scores)} scores. Updating database...")

# Fetch all pending jobs (using pagination)
offset = 0
limit = 1000
updated = 0

while True:
    r = db.table('job_queue').select('id, client_name, url, application_data').eq('status', 'PENDING').range(offset, offset + limit - 1).execute()
    data = r.data
    if not data:
        break
        
    for j in data:
        key = f"{j['client_name'].strip()}|{j['url'].strip()}"
        if key in csv_scores:
            score_val = csv_scores[key]
            # Get existing application_data or create empty dict
            app_data = j.get('application_data') or {}
            app_data['match_score'] = score_val
            
            db.table('job_queue').update({'application_data': app_data}).eq('id', j['id']).execute()
            updated += 1
            if updated % 100 == 0:
                print(f"Updated {updated} jobs...")
            
    offset += limit

print(f"Successfully injected scores into {updated} jobs in the database!")
