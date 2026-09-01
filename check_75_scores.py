from supabase import create_client
db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

ids = {
    'AWL-27275': 'SAI SHIVA JALIGAPU',
    'AWL-33056': 'MANIKANTA JAMMOJU',
    'AWL-31630': 'Anuhya yelisetty',
    'AWL-24852': 'Sankeerth Pasula',
    'AWL-30475': 'Manas Appasani'
}

print('--- Jobs with > 75% Score ---')
for aw_id, name in ids.items():
    r = db.table('job_queue').select('application_data').eq('applywizz_id', aw_id).execute()
    high_score_count = 0
    for row in r.data:
        app_data = row.get('application_data') or {}
        score = app_data.get('match_score', 0)
        try:
            if float(score) > 75:
                high_score_count += 1
        except:
            pass
    print(f'{name}: {high_score_count} high-score jobs')
    
