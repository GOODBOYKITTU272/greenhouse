from supabase import create_client
from collections import defaultdict

db = create_client('https://lnlvxsskkxeidlqgqqrj.supabase.co', 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImxubHZ4c3Nra3hlaWRscWdxcXJqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc4NzkzOTE2NSwiZXhwIjoyMTAzNTE1MTY1fQ.trCeN-N7Ufz5L8nkLaWzUaaEhR74GBqiyBI6J59jYLo')

client_stats = defaultdict(lambda: {'total': 0, 'pending': 0})

# Paginate to get ALL jobs in the DB
offset = 0
limit = 1000
while True:
    r = db.table('job_queue').select('client_name, status').range(offset, offset + limit - 1).execute()
    data = r.data
    if not data:
        break
        
    for j in data:
        name = str(j.get('client_name', 'Unknown')).strip()
        status = str(j.get('status', '')).upper()
        
        client_stats[name]['total'] += 1
        if status == 'PENDING':
            client_stats[name]['pending'] += 1
            
    offset += limit

# Sort by total jobs descending
sorted_clients = sorted(client_stats.items(), key=lambda x: x[1]['total'], reverse=True)

# Print top 10
print("--- TOP 10 CLIENTS ---")
for i, (name, stats) in enumerate(sorted_clients[:10], 1):
    print(f"{i}. {name} | Total Jobs: {stats['total']} | Pending: {stats['pending']}")

