import pandas as pd
import asyncio
import aiohttp
import time
import re

async def fetch_job_details(session, token, job_id):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs/{job_id}?questions=true&pay_transparency=true"
    try:
        async with session.get(url, timeout=10) as response:
            if response.status == 200:
                data = await response.json()
                
                # Extract Pay Range
                pay_ranges = data.get("pay_input_ranges", [])
                pay_info = ""
                if pay_ranges:
                    pr = pay_ranges[0]
                    pay_info = f"{pr.get('min_cents', 0)/100} - {pr.get('max_cents', 0)/100} {pr.get('currency_type', 'USD')}"
                
                # Extract Description (strip HTML tags for CSV readability)
                content_html = data.get("content", "")
                content_clean = re.sub('<[^<]+>', '', content_html).replace('\n', ' ').strip()
                
                # Questions
                questions = data.get("questions", [])
                q_labels = [q.get("label", "") for q in questions]
                
                return {
                    "salary_range": pay_info,
                    "description_snippet": content_clean[:200] + "..." if len(content_clean) > 200 else content_clean,
                    "application_questions": ", ".join(q_labels)
                }
    except Exception as e:
        print(f"Error fetching {token} {job_id}: {e}")
    return {"salary_range": "", "description_snippet": "", "application_questions": ""}

async def main():
    print("Loading 88 USA jobs from today...")
    df = pd.read_csv('usa_today_jobs.csv')
    
    start = time.time()
    
    # We will append the new data to the existing dataframe
    detailed_data = []
    
    async with aiohttp.ClientSession() as session:
        for idx, row in df.iterrows():
            token = row['greenhouse_token']
            url = str(row['job_url'])
            
            # Extract Job ID from URL: e.g. https://boards.greenhouse.io/okx/jobs/12345
            match = re.search(r'/jobs/(\d+)', url)
            if match:
                job_id = match.group(1)
                
                # Fetch details carefully to avoid ban
                details = await fetch_job_details(session, token, job_id)
                detailed_data.append(details)
                
                if idx % 10 == 0:
                    print(f"Fetched {idx+1}/{len(df)} jobs...")
                await asyncio.sleep(0.3) # Wait 300ms to avoid ban
            else:
                detailed_data.append({"salary_range": "", "description_snippet": "", "application_questions": ""})
                
    # Merge data back into dataframe
    df['salary_range'] = [d['salary_range'] for d in detailed_data]
    df['description_snippet'] = [d['description_snippet'] for d in detailed_data]
    df['application_questions'] = [d['application_questions'] for d in detailed_data]
    
    df.to_csv("usa_today_jobs_detailed.csv", index=False)
    
    print(f"Done in {time.time() - start:.2f} seconds!")
    print(f"Saved highly detailed job data to usa_today_jobs_detailed.csv")

if __name__ == "__main__":
    asyncio.run(main())
