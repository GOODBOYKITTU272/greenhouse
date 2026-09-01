import os
import time
import json
import logging
import requests
from supabase import create_client, Client

# Import our custom scripts (The Brain and The Muscle)
from applywizz_brain import ApplyWizzBrain
import applywizz_muscle

# Setup Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- CONFIGURATION ---
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://lnlvxsskkxeidlqgqqrj.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo")
BROWSERLESS_API_KEY = os.environ.get("BROWSERLESS_API_KEY", "cVwWrUw6ZoyibZVhcVwWrUw6ZoyibZVh")

def get_db_client() -> Client:
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def fetch_candidate_profile(applywizz_id: str, job_row: dict) -> dict:
    # ── Check if we already pre-fetched it into the database ──
    profile_data = job_row.get('client_profile')
    
    if profile_data:
        logging.info(f"Using PRE-FETCHED database profile for {applywizz_id}...")
    else:
        # ── Fallback to the live API ──
        logging.info(f"Fetching LIVE profile from API for {applywizz_id}...")
        api_url = f"https://www.apply-wizz.me/api/get-client-details?applywizz_id={applywizz_id}"
        resp = requests.get(api_url, timeout=15)
        if resp.status_code != 200:
            raise Exception(f"Failed to fetch profile: API returned {resp.status_code}")
        profile_data = resp.json()

    # The API returns 'client' and 'additional_information' objects inside the json
    client = profile_data.get("client", {})
    add_info = profile_data.get("additional_information", {})
    
    # Safely parse the name
    full_name = client.get("full_name", "Unknown Name")
    name_parts = full_name.split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""
    
    # Convert veteran text to boolean for fuzzy matcher
    vet_status = str(add_info.get("veteran_status", "")).lower()
    is_veteran = "not a protected veteran" not in vet_status and vet_status != ""
    
    candidate = {
        'first_name': first_name,
        'last_name': last_name,
        'email': client.get("personal_email", ""),
        'phone': client.get("callable_phone", ""),
        'linkedin': add_info.get("linked_in_url", ""),
        'website': add_info.get("github_url", ""),
        'resume_url': add_info.get("resume_url", ""),
        'cover_letter_url': add_info.get("cover_letter_path", ""),
        'visa_status': client.get("visa_type", "Citizen"),
        'salary_expectation': client.get("salary_range", "Open to discussion"),
        'veteran': add_info.get("veteran_status", ""),
        'gender': add_info.get("gender", ""),
        'race': add_info.get("race_ethnicity", ""),
        'disability': add_info.get("disability_status", "")
    }
    return candidate

def process_pending_jobs():
    supabase = get_db_client()
    
    logging.info("Checking database for PENDING jobs...")
    response = supabase.table("job_queue").select("*").eq("status", "PENDING").limit(2).execute()
    jobs = response.data
    
    if not jobs:
        logging.info("No PENDING jobs found. Sleeping...")
        return

    logging.info(f"Found {len(jobs)} jobs to process. Starting the engine...")

    for job in jobs:
        job_id = job['id']
        url = job['url']
        client_name = job['client_name']
        applywizz_id = job.get('applywizz_id')
        
        logging.info(f"--- Processing Job [{job_id}] for {client_name} ({applywizz_id}) ---")
        
        # Security: Delete any leftover answer map from the previous job so they can NEVER cross-contaminate
        if os.path.exists("answer_map.json"):
            os.remove("answer_map.json")
            
        try:
            if not applywizz_id:
                raise Exception("Row is missing applywizz_id")
                
            # STEP 1: Fetch the live candidate data
            candidate_profile = fetch_candidate_profile(applywizz_id, job)
            
            # STEP 2: The Brain (Resolve URL, fetch questions, fuzzy match answers)
            brain = ApplyWizzBrain(candidate_profile)
            brain.process_job(url) # This writes answer_map.json
            
            # Read the generated map (just to log it or verify)
            with open("answer_map.json", "r") as f:
                answer_map = json.load(f)
            
            # STEP 3: The Muscle (Submit via Browserless)
            # The muscle will read answer_map.json automatically
            applywizz_muscle.run_muscle("answer_map.json")
            
            # STEP 4: Update Database
            logging.info(f"Successfully applied for Job [{job_id}]!")
            supabase.table("job_queue").update({
                "status": "COMPLETED", 
                "error_message": None,
                "application_data": answer_map
            }).eq("id", job_id).execute()
                
        except Exception as e:
            error_msg = str(e)
            logging.error(f"Error on Job [{job_id}]: {error_msg}")
            
            # If answer_map exists, save it so we can see what questions caused the error
            app_data = None
            if 'answer_map' in locals():
                app_data = answer_map
                
            supabase.table("job_queue").update({
                "status": "ERROR", 
                "error_message": error_msg,
                "application_data": app_data
            }).eq("id", job_id).execute()
            
        time.sleep(2)

if __name__ == "__main__":
    process_pending_jobs()
