import pandas as pd
import asyncio
import aiohttp
import time

async def fetch_jobs(session, company, token):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                jobs = data.get("jobs", [])
                extracted = []
                for j in jobs:
                    extracted.append({
                        "company_name": company,
                        "greenhouse_token": token,
                        "job_title": j.get("title"),
                        "location": j.get("location", {}).get("name", "Remote/Unspecified"),
                        "updated_at": j.get("updated_at"),
                        "job_url": j.get("absolute_url")
                    })
                return extracted
    except Exception:
        pass
    return []

async def main():
    print("Loading the 93 confirmed Greenhouse companies...")
    df = pd.read_csv('greenhouse_hiring_companies.csv')
    
    start = time.time()
    all_jobs = []
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _, row in df.iterrows():
            tasks.append(fetch_jobs(session, row['original_name'], row['greenhouse_token']))
            
        print("Fetching all job postings concurrently...")
        results = await asyncio.gather(*tasks)
        
        for res in results:
            all_jobs.extend(res)
            
    jobs_df = pd.DataFrame(all_jobs)
    jobs_df.to_csv("all_open_jobs.csv", index=False)
    
    print(f"Done in {time.time() - start:.2f} seconds!")
    print(f"Successfully extracted {len(jobs_df)} total job postings across all 93 companies.")

if __name__ == "__main__":
    asyncio.run(main())
