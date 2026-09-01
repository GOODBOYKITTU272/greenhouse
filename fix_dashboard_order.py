with open('admin_dashboard.html', 'r') as f:
    text = f.read()

# Fix Supabase fetch limit issue (only returning 1000 oldest jobs)
old_fetch = "const { data, error } = await supabaseClient.from('job_queue').select('*').limit(3000);"
new_fetch = "const { data, error } = await supabaseClient.from('job_queue').select('*').order('id', { ascending: false }).limit(3000);"

text = text.replace(old_fetch, new_fetch)

with open('admin_dashboard.html', 'w') as f:
    f.write(text)
print("Dashboard order fixed!")
