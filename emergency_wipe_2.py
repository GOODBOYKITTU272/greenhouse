from supabase import create_client

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

r = db.table('job_queue').select('id, application_data').eq('applywizz_id', 'AWL-25629').in_('status', ['APPROVED', 'NEEDS_REVIEW']).execute()

for job in r.data:
    if not job.get('application_data'): continue
    app_data = job['application_data']
    modified = False
    
    for q in app_data.get('answer_map', []):
        ans = str(q.get('answer', ''))
        # If the AI tried to put the Amazon AWS resume link into a text box (like Website or LinkedIn)
        if 'amazonaws.com' in ans.lower():
            q['answer'] = ''
            modified = True
            
    if modified:
        db.table('job_queue').update({'application_data': app_data}).eq('id', job['id']).execute()
        print(f"Wiped AWS link from job {job['id']}")
print("Emergency DB wipe complete.")
