with open('brain_worker.py', 'r') as f:
    text = f.read()

text = text.replace(
    "r = supabase.table('job_queue').select('*').eq('status', 'PENDING').limit(5).execute()",
    "r = supabase.table('job_queue').select('*').eq('status', 'PENDING').in_('applywizz_id', ['AWL-29876', 'AWL-26410', 'AWL-30341', 'AWL-25073', 'AWL-30563', 'AWL-26271', 'AWL-30711', 'AWL-17476', 'AWL-25629']).limit(20).execute()"
)

with open('brain_worker.py', 'w') as f:
    f.write(text)
