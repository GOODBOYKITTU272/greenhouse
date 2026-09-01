import csv
import os
import requests

SUPABASE_URL = "https://lnlvxsskkxeidlqgqqrj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo"

file_path = "/Users/ramakrishnachanda/Desktop/greenhosue/greenhouse(Sheet1).csv"

with open(file_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=',')
    
    rows_to_insert = []
    for row in reader:
        url = row.get("url")
        applywizz_id = row.get("Applywizz ID")
        
        if applywizz_id == "AWL-29876" and url:
            record = {
                "applywizz_id": applywizz_id,
                "client_name": row.get("Client Name", "Unknown Candidate"),
                "url": url,
                "status": "PENDING"
            }
            rows_to_insert.append(record)

    if rows_to_insert:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal"
        }
        r = requests.post(f"{SUPABASE_URL}/rest/v1/job_queue", headers=headers, json=rows_to_insert)
        print(f"Status Code: {r.status_code}")
        print(f"Response: {r.text}")
