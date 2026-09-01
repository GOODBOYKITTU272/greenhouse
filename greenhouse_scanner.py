import pandas as pd
import asyncio
import aiohttp
import re
import time
import argparse
import sys

async def check_board(session, company, token, sem, proxy):
    url = f"https://boards-api.greenhouse.io/v1/boards/{token}/jobs"
    async with sem:
        try:
            async with session.get(url, proxy=proxy, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    jobs = data.get("jobs", [])
                    company_name = data.get("name", "")
                    if jobs:
                        return {
                            "original_name": company,
                            "greenhouse_token": token,
                            "greenhouse_name": company_name,
                            "jobs_count": len(jobs),
                            "url": f"https://boards.greenhouse.io/{token}"
                        }
        except Exception:
            pass 
    return None

async def process_companies(df_subset, concurrency, proxy, worker_id):
    results = []
    sem = asyncio.Semaphore(concurrency)
    connector = aiohttp.TCPConnector(limit=concurrency)
    
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for company in df_subset['company'].dropna().unique():
            company_str = str(company).strip()
            if not company_str:
                continue
                
            token1 = re.sub(r'[^a-zA-Z0-9]', '', company_str).lower()
            if token1:
                tasks.append(check_board(session, company_str, token1, sem, proxy))
            
            token2 = re.sub(r'\s+', '-', company_str).lower()
            token2 = re.sub(r'[^a-z0-9\-]', '', token2).strip('-')
            
            if token2 and token2 != token1:
                tasks.append(check_board(session, company_str, token2, sem, proxy))
                
        print(f"[Worker {worker_id}] Checking {len(tasks)} tokens...")
        
        batch_size = 500
        for i in range(0, len(tasks), batch_size):
            batch = tasks[i:i+batch_size]
            batch_results = await asyncio.gather(*batch)
            valid = [r for r in batch_results if r is not None]
            results.extend(valid)
            print(f"[Worker {worker_id}] Progress: {min(i+batch_size, len(tasks))}/{len(tasks)} | Found: {len(results)}")
            await asyncio.sleep(0.1)
            
    return results

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str, required=True)
    parser.add_argument("--output", type=str, required=True)
    parser.add_argument("--proxy", type=str, default=None)
    parser.add_argument("--concurrency", type=int, default=50)
    parser.add_argument("--worker_id", type=str, default="1")
    args = parser.parse_args()

    try:
        df = pd.read_csv(args.input)
    except Exception as e:
        print(f"[Worker {args.worker_id}] Error reading {args.input}: {e}")
        sys.exit(1)
        
    print(f"[Worker {args.worker_id}] Started with {len(df)} companies.")
    start = time.time()
    results = asyncio.run(process_companies(df, args.concurrency, args.proxy, args.worker_id))
    
    unique_results = {r['greenhouse_token']: r for r in results}.values()
    found_df = pd.DataFrame(list(unique_results))
    
    if not found_df.empty:
        found_df = found_df.sort_values(by='jobs_count', ascending=False)
        found_df.to_csv(args.output, index=False)
    else:
        # Create empty file with headers
        pd.DataFrame(columns=["original_name", "greenhouse_token", "greenhouse_name", "jobs_count", "url"]).to_csv(args.output, index=False)

    print(f"[Worker {args.worker_id}] Finished in {time.time()-start:.2f}s. Saved to {args.output}")

if __name__ == "__main__":
    main()
