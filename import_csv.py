import csv
from supabase import create_client
import sys

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

filename = "/Users/ramakrishnachanda/Desktop/greenhosue/Greenhouse 1.csv"
batch_size = 500

print(f"Reading {filename}...")
with open(filename, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

total = len(rows)
print(f"Total jobs to import: {total}")

imported = 0
current_batch = []

for row in rows:
    # Handle CSV quoting or missing data
    client_name = row.get('Client Name', '').strip()
    aw_id = row.get('Applywizz ID', '').strip()
    url = row.get('url', '').strip()
    
    if not client_name or not aw_id or not url:
        continue
        
    current_batch.append({
        'client_name': client_name,
        'applywizz_id': aw_id,
        'url': url,
        'status': 'PENDING'
    })
    
    if len(current_batch) >= batch_size:
        try:
            db.table('job_queue').insert(current_batch).execute()
            imported += len(current_batch)
            print(f"Imported {imported}/{total}...")
            current_batch = []
        except Exception as e:
            print(f"Error inserting batch: {e}")
            sys.exit(1)

if current_batch:
    db.table('job_queue').insert(current_batch).execute()
    imported += len(current_batch)

print(f"Successfully imported {imported} jobs into the database!")
