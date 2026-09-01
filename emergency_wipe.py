from supabase import create_client
import time

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

r = db.table('job_queue').select('id, application_data').eq('applywizz_id', 'AWL-25629').eq('status', 'NEEDS_REVIEW').execute()

for job in r.data:
    if not job.get('application_data'): continue
    app_data = job['application_data']
    modified = False
    
    for q in app_data.get('answer_map', []):
        label = q.get('question_label', '').lower()
        ans = q.get('answer', '')
        
        # 1. Nuke Cover Letter if it's just his name
        if 'cover letter' in label and 'srujan' in str(ans).lower() and len(str(ans)) < 30:
            q['answer'] = ''
            modified = True
            
        # 2. Nuke County if it's N/A
        if 'county' in label and ans == 'N/A':
            q['answer'] = ''
            modified = True
            
        # 3. Fix Race to Asian if it fell to "prefer to self-describe" or "decline"
        if 'race' in label or 'racial' in label or 'ethnic' in label:
            if 'self-describe' in str(ans).lower() or 'decline' in str(ans).lower() or 'wish to answer' in str(ans).lower():
                # We need to find the Asian option if it exists in options_for_ai
                opts = q.get('options_for_ai', [])
                for opt in opts:
                    if 'Asian' in opt:
                        q['answer'] = opt
                        modified = True
                        break
                        
    if modified:
        db.table('job_queue').update({'application_data': app_data}).eq('id', job['id']).execute()
        print(f"Cleaned up job {job['id']}")
print("Emergency cleanup complete.")
