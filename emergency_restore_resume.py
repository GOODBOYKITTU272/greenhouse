from supabase import create_client

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

r = db.table('job_queue').select('id, application_data').eq('applywizz_id', 'AWL-25629').in_('status', ['APPROVED', 'NEEDS_REVIEW']).execute()

for job in r.data:
    if not job.get('application_data'): continue
    app_data = job['application_data']
    modified = False
    
    for q in app_data.get('answer_map', []):
        label = q.get('question_label', '').lower()
        
        # Restore the Resume URL that I accidentally wiped
        if 'resume' in label or 'cv' in label:
            if q.get('answer', '') == '':
                q['answer'] = 'https://applywizz-prod.s3.us-east-2.amazonaws.com/CRM/AWL-25629-10042026-0504-resume_srujan-maryala_pm.pdf'
                modified = True
                
    if modified:
        db.table('job_queue').update({'application_data': app_data}).eq('id', job['id']).execute()
        print(f"Restored Resume link for job {job['id']}")
print("Emergency DB restore complete.")
