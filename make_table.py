import pandas as pd
df = pd.read_csv('master_greenhouse_jobs.csv')
with open('/Users/ramakrishnachanda/.gemini/antigravity/brain/510d8589-fbca-47ba-bf26-b31437aec19e/greenhouse_279_companies.md', 'w') as f:
    f.write('# 🏢 279 Confirmed Greenhouse Companies\n\n')
    f.write('These are the companies we successfully verified before the IP ban interrupted the scan.\n\n')
    f.write('| Original Name | Greenhouse ID | Open Jobs | Board Link |\n')
    f.write('|---|---|---|---|\n')
    for _, row in df.iterrows():
        f.write(f"| {row['original_name']} | `{row['greenhouse_token']}` | {row['jobs_count']} | [View Board]({row['url']}) |\n")
