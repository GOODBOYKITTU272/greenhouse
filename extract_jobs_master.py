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
    df = pd.read_csv('master_greenhouse_jobs.csv')
    
    start = time.time()
    all_jobs = []
    
    async with aiohttp.ClientSession() as session:
        tasks = []
        for _, row in df.iterrows():
            tasks.append(fetch_jobs(session, row['original_name'], row['greenhouse_token']))
            
        results = await asyncio.gather(*tasks)
        for res in results:
            all_jobs.extend(res)
            
    jobs_df = pd.DataFrame(all_jobs)
    jobs_df.to_csv("all_open_jobs_master.csv", index=False)
    
    us_keywords = ['United States', 'US', 'Remote - US', 'AL', 'AK', 'AZ', 'AR', 'CA', 'CO', 'CT', 'DE', 'FL', 'GA', 'HI', 'ID', 'IL', 'IN', 'IA', 'KS', 'KY', 'LA', 'ME', 'MD', 'MA', 'MI', 'MN', 'MS', 'MO', 'MT', 'NE', 'NV', 'NH', 'NJ', 'NM', 'NY', 'NC', 'ND', 'OH', 'OK', 'OR', 'PA', 'RI', 'SC', 'SD', 'TN', 'TX', 'UT', 'VT', 'VA', 'WA', 'WV', 'WI', 'WY', 'DC']

    def is_us(loc):
        if pd.isna(loc): return False
        loc = str(loc)
        words = loc.replace(',', ' ').split()
        if 'US' in words or 'United States' in loc: return True
        for w in words:
            if w in us_keywords: return True
        return False

    df_us = jobs_df[jobs_df['location'].apply(is_us)]
    
    df_us['updated_at'] = pd.to_datetime(df_us['updated_at'], utc=True)
    now = pd.Timestamp.now(tz='UTC')
    df_today = df_us[df_us['updated_at'] >= now - pd.Timedelta(days=1)]
    
    print(f"Total jobs from all 279 companies: {len(jobs_df)}")
    print(f"Total USA jobs from 279 companies: {len(df_us)}")
    print(f"Total USA jobs updated today: {len(df_today)}")

if __name__ == "__main__":
    asyncio.run(main())
