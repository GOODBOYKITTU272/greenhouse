import pandas as pd
import glob
import os

def main():
    result_files = glob.glob("results_worker_*.csv")
    if not result_files:
        print("No worker results found!")
        return
        
    dfs = []
    for f in result_files:
        try:
            df = pd.read_csv(f)
            if not df.empty:
                dfs.append(df)
        except Exception:
            pass

    if dfs:
        master_df = pd.concat(dfs, ignore_index=True)
        # Deduplicate globally
        master_df = master_df.drop_duplicates(subset=["greenhouse_token"])
        master_df = master_df.sort_values(by="jobs_count", ascending=False)
        master_df.to_csv("master_greenhouse_jobs.csv", index=False)
        print(f"Successfully aggregated {len(result_files)} files!")
        print(f"Total unique companies found: {len(master_df)}")
        print(f"Saved to master_greenhouse_jobs.csv")
    else:
        print("All worker files were empty.")
        
    # Cleanup
    for f in glob.glob("chunk_*.csv") + result_files:
        os.remove(f)
    print("Cleaned up temporary chunk files.")

if __name__ == "__main__":
    main()
