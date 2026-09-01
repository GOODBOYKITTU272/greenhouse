import os, time, json, logging, sys
sys.path.insert(0, '/Users/ramakrishnachanda/Desktop/greenhosue')
from supabase import create_client
from applywizz_brain import ApplyWizzBrain
from brain_worker import get_or_cache_candidate, build_candidate_dict
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s: %(message)s', filename='brain_fix.log', filemode='w')
SUPABASE_URL = 'https://lnlvxsskkxeidlqgqqrj.supabase.co'
SUPABASE_KEY = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo'
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TARGET = 'AWL-25629'

# Clear bad memory bank entries
supabase.table('ai_memory_bank').delete().eq('applywizz_id', TARGET).execute()

jobs = supabase.table('job_queue').select('*').in_('status', ['PENDING', 'NEEDS_REVIEW', 'ERROR']).eq('applywizz_id',TARGET).execute().data
logging.info(f'Processing {len(jobs)} jobs for Srujan with ONE-BY-ONE architecture...')
for job in jobs:
    job_id = job['id']
    if os.path.exists('answer_map.json'): os.remove('answer_map.json')
    try:
        cached = get_or_cache_candidate(supabase, TARGET)
        candidate = build_candidate_dict(TARGET, cached['profile_json'])
        resume_text = cached['resume_text']
        brain = ApplyWizzBrain(candidate, memory_bank={}, resume_text=resume_text)
        brain.process_job(job['url'])
        with open('answer_map.json') as f:
            answer_map = json.load(f)
        supabase.table('job_queue').update({'status':'NEEDS_REVIEW','error_message':None,'application_data':answer_map}).eq('id',job_id).execute()
        logging.info(f'Job [{job_id}] -> NEEDS_REVIEW')
    except Exception as e:
        logging.error(f'Job [{job_id}] ERROR: {e}')
print("DONE PROCESSING ALL JOBS!")
