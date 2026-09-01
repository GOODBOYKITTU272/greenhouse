import csv

top_10_clients = [
    "LOKESH ADDANKI",
    "Sreelekha Meenugu",
    "SAI SHIVA JALIGAPU",
    "Deekshith Reddy Cheruvu Belagal",
    "vamshi adhe",
    "Rohith Bachati",
    "Vamshi Challagundla",
    "Akshaya Manne",
    "MANIKANTA JAMMOJU",
    "Anuhya yelisetty"
]
# Convert to lowercase for safer matching
top_10_lower = [name.lower() for name in top_10_clients]

highest_jobs = {name: [] for name in top_10_lower}

with open("/Users/ramakrishnachanda/Desktop/greenhosue/Greenhouse 1.csv", "r", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        client_name = row.get("Client Name", "").strip().lower()
        if client_name in top_10_lower:
            score = row.get("score", "0")
            try:
                score = float(score)
            except:
                score = 0.0
                
            job_url = row.get("url", "")
            status = row.get("status", "PENDING")
            
            if status.upper() == "PENDING":
                highest_jobs[client_name].append({"score": score, "url": job_url, "real_name": row.get("Client Name", "").strip()})

print("--- HIGHEST SCORING PENDING JOBS FOR YOUR TOP 10 CLIENTS ---")
for name_lower in top_10_lower:
    jobs = highest_jobs[name_lower]
    if not jobs:
        # Let's find the original case name
        original_name = next((n for n in top_10_clients if n.lower() == name_lower), name_lower)
        print(f"\n👤 {original_name}:")
        print("  ❌ No jobs found with scores in the recent CSV (these jobs might be from an older upload).")
        continue
        
    # Sort by score descending
    jobs.sort(key=lambda x: x["score"], reverse=True)
    
    real_name = jobs[0]["real_name"]
    print(f"\n👤 {real_name}:")
    # Show the top 3 highest scoring jobs for this client
    for i, j in enumerate(jobs[:3], 1):
        print(f"  {i}. Score: {int(j['score'])} | Job: {j['url']}")
        
