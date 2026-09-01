import pandas as pd
import asyncio
import aiohttp
import time
import os
from datetime import datetime, timedelta, timezone

async def fetch_jobs(session, token, proxy):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        async with session.get(url, proxy=proxy, timeout=15) as response:
            if response.status == 200:
                data = await response.json()
                return token, data.get("jobs", [])
    except Exception as e:
        pass
    return token, []

async def bound_fetch(sem, session, token, proxy):
    async with sem:
        return await fetch_jobs(session, token, proxy)

async def main():
    print("Loading 2,031 companies...")
    df = pd.read_csv("master_greenhouse_jobs.csv")
    tokens = df["greenhouse_token"].dropna().unique()
    
    # Load Proxies
    proxies = []
    if os.path.exists("proxies.txt"):
        with open("proxies.txt", "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    parts = line.split(':')
                    if len(parts) == 4:
                        proxies.append(f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}")
    
    if not proxies:
        print("No proxies found!")
        return

    print(f"Loaded {len(proxies)} proxies. Starting fast extraction...")
    
    sem = asyncio.Semaphore(30) # 30 concurrent requests
    all_jobs = []
    
    start = time.time()
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for i, token in enumerate(tokens):
            proxy = proxies[i % len(proxies)]
            tasks.append(bound_fetch(sem, session, token, proxy))
            
        results = await asyncio.gather(*tasks)
        
        for token, jobs in results:
            for job in jobs:
                loc = job.get("location", {}).get("name", "")
                title = job.get("title", "")
                url = job.get("absolute_url", "")
                updated_at = job.get("updated_at", "")
                
                all_jobs.append({
                    "company_token": token,
                    "job_title": title,
                    "location": loc,
                    "job_url": url,
                    "updated_at": updated_at
                })
                
    print(f"\nExtracted {len(all_jobs)} total jobs in {time.time() - start:.2f} seconds!")
    
    jobs_df = pd.DataFrame(all_jobs)
    jobs_df.to_csv("all_2031_jobs.csv", index=False)
    
    # Filter for USA and Last 24 Hours
    now = datetime.now(timezone.utc)
    one_day_ago = now - timedelta(days=1)
    
    # Parse dates safely
    jobs_df['updated_at_dt'] = pd.to_datetime(jobs_df['updated_at'], errors='coerce', utc=True)
    
    # Filter by time
    recent_jobs = jobs_df[jobs_df['updated_at_dt'] >= one_day_ago]
    
    # Filter by USA location (simple string matching for common US terms/states)
    us_keywords = ['US', 'USA', 'United States', 'New York', 'NY', 'San Francisco', 'CA', 'California', 'Texas', 'TX', 'Remote - US', 'Remote (US)']
    
    def is_usa(loc):
        loc = str(loc).upper()
        # Direct matches
        if 'USA' in loc or 'UNITED STATES' in loc: return True
        # State abbreviations with word boundaries
        import re
        if re.search(r'\b(AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY)\b', loc):
            return True
        return False
        
    usa_recent = recent_jobs[recent_jobs['location'].apply(is_usa)]
    
    usa_recent.to_csv("final_usa_24h_jobs.csv", index=False)
    
    total_jobs_found = len(usa_recent)
    unique_companies = usa_recent['company_token'].nunique()
    
    print("\n--- FINAL RESULTS ---")
    print(f"Jobs posted in the USA in the last 24 hours: {total_jobs_found}")
    print(f"Number of distinct companies hiring today: {unique_companies}")

if __name__ == "__main__":
    asyncio.run(main())
