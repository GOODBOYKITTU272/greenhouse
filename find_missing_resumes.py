from supabase import create_client

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

# 1. Get all profiles we ALREADY have
r1 = db.table('candidate_profiles').select('applywizz_id').execute()
existing_profiles = set([p['applywizz_id'] for p in r1.data])

# 2. Get all jobs in the queue
missing = {}
offset = 0
limit = 1000
while True:
    r2 = db.table('job_queue').select('client_name, applywizz_id').range(offset, offset + limit - 1).execute()
    data = r2.data
    if not data:
        break
    
    for j in data:
        aw_id = j.get('applywizz_id')
        name = j.get('client_name')
        if aw_id and aw_id not in existing_profiles:
            missing[aw_id] = name
            
    offset += limit

print(f"Total missing resumes needed: {len(missing)}")
print("--- TOP 20 MISSING CLIENTS ---")
for i, (aw_id, name) in enumerate(list(missing.items())[:20], 1):
    print(f"{aw_id} | {name}")
    
