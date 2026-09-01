import csv
import sys
from supabase import create_client

# --- CONFIGURATION ---
SUPABASE_URL = "https://lnlvxsskkxeidlqgqqrj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def push_jobs_to_supabase():
    # Looking at the file you just put in the folder
    file_path = "/Users/ramakrishnachanda/Desktop/greenhosue/greenhouse(Sheet1).csv"
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            # You downloaded a CSV, so the delimiter is a comma
            reader = csv.DictReader(f, delimiter=',')
            
            rows_to_insert = []
            for row in reader:
                # Safely get the URL and Client Name, ignoring empty rows
                url = row.get("url")
                if not url:
                    continue
                    
                record = {
                    "applywizz_id": row.get("Applywizz ID"),
                    "client_name": row.get("Client Name", "Unknown Candidate"),
                    "url": url,
                    "status": "PENDING"
                }
                rows_to_insert.append(record)

            if not rows_to_insert:
                print("No rows found! Make sure jobs.tsv has headers: 'Client Name' and 'url'")
                return

            print(f"Found {len(rows_to_insert)} jobs. Pushing to Supabase in chunks...")
            
            # Supabase prefers inserts in chunks of 500
            for i in range(0, len(rows_to_insert), 500):
                chunk = rows_to_insert[i:i+500]
                supabase.table("job_queue").insert(chunk).execute()
                print(f"✅ Inserted {len(chunk)} rows...")
                
            print("🚀 Successfully pushed ALL jobs to PENDING!")

    except FileNotFoundError:
        print(f"❌ Error: Could not find the file at {file_path}")
        print("Please save your data as 'jobs.tsv' in the greenhosue folder.")
    except Exception as e:
        print(f"❌ Error during insert: {str(e)}")
        print("Make sure your Supabase table 'job_queue' has columns: client_name, url, status")

if __name__ == "__main__":
    push_jobs_to_supabase()
