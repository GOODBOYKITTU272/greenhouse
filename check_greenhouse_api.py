import pandas as pd
import asyncio
import aiohttp
import re
import time

async def check_board(session, company, token):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    try:
        async with session.get(url, timeout=5) as response:
            if response.status == 200:
                data = await response.json()
                jobs = data.get("jobs", [])
                return {"company": company, "token": token, "status": "Found", "jobs_count": len(jobs)}
            else:
                return {"company": company, "token": token, "status": "Not Found", "jobs_count": 0}
    except Exception as e:
        return {"company": company, "token": token, "status": "Error", "jobs_count": 0}

async def process_companies(df_subset):
    results = []
    async with aiohttp.ClientSession() as session:
        tasks = []
        for company in df_subset['company'].dropna().unique():
            # Basic token generation: lowercase, replace spaces with nothing or hyphens
            token = re.sub(r'[^a-zA-Z0-9]', '', str(company)).lower()
            if token:
                tasks.append(check_board(session, company, token))
            
            # Maybe also try with hyphens
            token_hyphen = re.sub(r'[^a-zA-Z0-9]', '-', str(company)).strip('-').lower()
            if token_hyphen and token_hyphen != token:
                tasks.append(check_board(session, company, token_hyphen))
                
        # Run concurrently in batches to avoid too many connections
        chunk_size = 50
        for i in range(0, len(tasks), chunk_size):
            chunk = tasks[i:i+chunk_size]
            chunk_results = await asyncio.gather(*chunk)
            results.extend(chunk_results)
            print(f"Processed {min(i+chunk_size, len(tasks))}/{len(tasks)} tokens...")
            await asyncio.sleep(0.5)
            
    return results

def main():
    print("Loading cleaned_companies.csv...")
    df = pd.read_csv('cleaned_companies.csv')
    
    # Taking a small sample of 1000 for demonstration
    sample_size = 1000
    df_subset = df.head(sample_size)
    print(f"Checking {sample_size} companies against Greenhouse API...")
    
    start = time.time()
    results = asyncio.run(process_companies(df_subset))
    print(f"Finished in {time.time() - start:.2f} seconds.")
    
    # Filter only found boards
    found = [r for r in results if r['status'] == 'Found']
    found_df = pd.DataFrame(found)
    
    if not found_df.empty:
        print("\nFound Greenhouse Boards:")
        print(found_df.sort_values(by='jobs_count', ascending=False))
        found_df.to_csv('greenhouse_found.csv', index=False)
        print("\nSaved found boards to greenhouse_found.csv")
    else:
        print("\nNo Greenhouse boards found in this sample.")

if __name__ == "__main__":
    main()
