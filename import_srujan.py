import csv
from supabase import create_client

SUPABASE_URL = "https://lnlvxsskkxeidlqgqqrj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

file_path = "/Users/ramakrishnachanda/Desktop/greenhosue/greenhouse(Sheet1).csv"

with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=',')
    
    rows_to_insert = []
    for row in reader:
        url = row.get("url")
        applywizz_id = row.get("Applywizz ID")
        
        if applywizz_id == "AWL-25629" and url:
            record = {
                "applywizz_id": applywizz_id,
                "client_name": row.get("Client Name", "Unknown Candidate"),
                "url": url,
                "status": "PENDING"
            }
            rows_to_insert.append(record)

    if not rows_to_insert:
        print("No jobs found for AWL-25629!")
    else:
        print(f"Found {len(rows_to_insert)} jobs for AWL-25629. Pushing to Supabase...")
        for i in range(0, len(rows_to_insert), 500):
            chunk = rows_to_insert[i:i+500]
            supabase.table("job_queue").insert(chunk).execute()
        print("✅ Successfully imported Srujan's jobs!")
