import requests
import json
import time
from supabase import create_client

SUPABASE_URL = "https://lnlvxsskkxeidlqgqqrj.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

print("="*50)
print("📥 APPLYWIZZ PRE-FETCHER (Limiting to 15 Jobs)")
print("="*50)

# 1. Get 15 jobs that don't have a profile saved yet
response = supabase.table("job_queue").select("*").eq("status", "PENDING").is_("client_profile", "null").limit(15).execute()
jobs = response.data

if not jobs:
    print("No pending jobs found without a profile!")
    exit()

print(f"Found {len(jobs)} jobs. Fetching from API and saving to Supabase...\n")

for job in jobs:
    job_id = job['id']
    applywizz_id = job['applywizz_id']
    
    print(f"Fetching API for {applywizz_id} (Job {job_id})...")
    
    try:
        api_url = f"https://www.apply-wizz.me/api/get-client-details?applywizz_id={applywizz_id}"
        resp = requests.get(api_url, timeout=10)
        
        if resp.status_code == 200:
            profile_json = resp.json()
            
            # Save it permanently into Supabase
            supabase.table("job_queue").update({
                "client_profile": profile_json
            }).eq("id", job_id).execute()
            
            print(f"   ✅ Saved profile to database!")
        else:
            print(f"   ❌ API returned {resp.status_code}")
            
    except Exception as e:
        print(f"   ❌ Failed to fetch: {e}")
        
    time.sleep(0.5) # Be nice to the API

print("\n🎉 Pre-fetching complete! Those 15 jobs are now permanently stored in Supabase.")
