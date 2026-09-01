import csv
from supabase import create_client

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

top_10 = [
    "LOKESH ADDANKI", "Sreelekha Meenugu", "SAI SHIVA JALIGAPU",
    "Deekshith Reddy Cheruvu Belagal", "vamshi adhe", "Rohith Bachati",
    "Vamshi Challagundla", "Akshaya Manne", "MANIKANTA JAMMOJU", "Anuhya yelisetty"
]
top_10_lower = [n.lower() for n in top_10]

print("Reading CSV and finding top 10 client scores...")
updates = []
with open("/Users/ramakrishnachanda/Desktop/greenhosue/Greenhouse 1.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        client = row.get('Client Name', '').strip()
        if client.lower() in top_10_lower:
            url = row.get('url', '').strip()
            score = row.get('score', '0')
            updates.append({"client": client, "url": url, "score": score})

print(f"Found {len(updates)} scores for the Top 10 clients. Injecting into DB...")

# Fetch only jobs for these clients
for client_name in top_10:
    r = db.table('job_queue').select('id, url, application_data').eq('client_name', client_name).eq('status', 'PENDING').execute()
    if not r.data: continue
    
    for j in r.data:
        # Find matching score
        match = next((u['score'] for u in updates if u['url'] == j['url'] and u['client'].lower() == client_name.lower()), None)
        if match:
            app_data = j.get('application_data') or {}
            app_data['match_score'] = match
            db.table('job_queue').update({'application_data': app_data}).eq('id', j['id']).execute()

print("Finished injecting scores for the Top 10 clients!")
