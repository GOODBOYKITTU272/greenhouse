import csv, os, sys
sys.path.insert(0, '/Users/ramakrishnachanda/Desktop/greenhosue')
from supabase import create_client

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

csv_files = ['Greenhouse 1.csv', 'greenhouse(Sheet1).csv']
target_id = 'AWL-25629'
found_urls = set()

# Get existing URLs from DB to avoid duplicates
existing = db.table('job_queue').select('url').eq('applywizz_id', target_id).execute()
db_urls = {j['url'] for j in existing.data}
print(f"Already in DB: {len(db_urls)} jobs")

for file in csv_files:
    if not os.path.exists(file): continue
    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.reader(f)
        for row in reader:
            if not row: continue
            # Check if AWL-25629 or Srujan is in the row
            row_str = " ".join(row)
            if target_id in row_str or 'Srujan Maryala' in row_str:
                # Find the URL in the row (usually starts with http)
                for cell in row:
                    if cell.startswith('http'):
                        url = cell.strip()
                        if url not in db_urls and url not in found_urls:
                            found_urls.add(url)
                            db.table('job_queue').insert({
                                'applywizz_id': target_id,
                                'client_name': 'Srujan Maryala',
                                'url': url,
                                'status': 'PENDING'
                            }).execute()
                            print(f"Imported NEW job from {file}: {url}")

print(f"Total new jobs imported for Srujan: {len(found_urls)}")
