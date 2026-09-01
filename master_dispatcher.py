import pandas as pd
import numpy as np
import subprocess
import os
import argparse
import time
import glob

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default="cleaned_companies.csv")
    parser.add_argument("--workers", type=int, default=30)
    parser.add_argument("--proxy_file", type=str, default=None)
    args = parser.parse_args()

    df = pd.read_csv(args.input)
    print(f"[Master] Loaded {len(df)} companies.")
    
    for f in glob.glob("chunk_*.csv") + glob.glob("results_worker_*.csv"):
        os.remove(f)

    chunks = np.array_split(df, args.workers)
    
    proxies = []
    if args.proxy_file:
        with open(args.proxy_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line:
                    # Format: IP:PORT:USER:PASS
                    parts = line.split(':')
                    if len(parts) == 4:
                        proxy = f"http://{parts[2]}:{parts[3]}@{parts[0]}:{parts[1]}"
                        proxies.append(proxy)
        print(f"[Master] Loaded {len(proxies)} proxies from {args.proxy_file}.")

    processes = []
    start = time.time()
    
    for i, chunk in enumerate(chunks):
        worker_id = i + 1
        input_file = f"chunk_{worker_id}.csv"
        output_file = f"results_worker_{worker_id}.csv"
        
        chunk.to_csv(input_file, index=False)
        print(f"[Master] Spawned Worker {worker_id} ({len(chunk)} companies)")
        
        cmd = [
            "python3", "greenhouse_scanner.py", 
            "--input", input_file, 
            "--output", output_file,
            "--worker_id", str(worker_id)
        ]
        
        if proxies:
            worker_proxy = proxies[i % len(proxies)]
            cmd.extend(["--proxy", worker_proxy])
            
        p = subprocess.Popen(cmd)
        processes.append(p)
        
    print(f"\n[Master] All {args.workers} workers running in parallel! Waiting for completion...\n")
    
    for p in processes:
        p.wait()
        
    print(f"\n[Master] All workers finished in {time.time() - start:.2f} seconds!")
    print("[Master] Run 'python3 aggregator.py' to merge the results.")

if __name__ == "__main__":
    main()
