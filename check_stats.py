import os
from supabase import create_client

SUPABASE_URL = "https://lnlvxsskkxeidlqgqqrj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo"

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("\n--- APPLYWIZZ DATABASE STATS ---")
response = supabase.table("job_queue").select("status, client_name, url").execute()
jobs = response.data

completed = [j for j in jobs if j['status'] == 'COMPLETED']
failed = [j for j in jobs if j['status'] == 'FAILED']
pending = [j for j in jobs if j['status'] == 'PENDING']

print(f"✅ COMPLETED: {len(completed)}")
print(f"❌ FAILED: {len(failed)}")
print(f"⏳ PENDING: {len(pending)}")
print("--------------------------------")

if completed:
    print("\nRecent Completed Applications:")
    for j in completed[-5:]:
        print(f" - {j['client_name']} -> {j['url']}")
