with open('brain_worker.py', 'r') as f:
    text = f.read()

import re

# Find the exact select statement and replace it
target = 'response = supabase.table("job_queue").select("*").eq("status", "PENDING").limit(5).execute()'
replacement = 'response = supabase.table("job_queue").select("*").eq("status", "PENDING").in_("applywizz_id", ["AWL-33056", "AWL-27275", "AWL-31630", "AWL-24852"]).limit(10).execute()'

if target in text:
    text = text.replace(target, replacement)
    with open('brain_worker.py', 'w') as f:
        f.write(text)
    print("Worker perfectly focused on the 4 candidates!")
else:
    print("Could not find the target string!")
