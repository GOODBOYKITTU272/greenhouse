"""
Import a daily job-match CSV/Excel file into job_queue.

Expected columns (exact names, case-insensitive): Date, Applywizz ID,
Client Name, url, score, scored_jobId, status.

Only status == PENDING rows are imported — this matches what's been
confirmed about the daily feed: every future export is PENDING-only, and
this script is deliberately built to only ever act on that, never on
COMPLETED/ALREADY_APPLIED/IN_PROGRESS rows that showed up in one earlier,
contaminated file.

Safety rules, all deliberate:
  - Skip a row if (applywizz_id, url) already exists anywhere in job_queue
    (any status) — never queue the same candidate for the same job twice.
  - Skip a row whose URL is already known-malformed (contains a second
    http:// or https:// inside it — the recurring urbancompass bug found
    twice this session) rather than queuing something guaranteed to fail
    and burning a worker cycle on it.
  - score and scored_jobId are never dropped — stored in
    application_data.source_csv so claim_next_approved_job() can order by
    score without any job_queue schema change.

Deliberately uses only the stdlib csv module + openpyxl (already used
elsewhere in this session for reading .xlsx scans) rather than pandas —
this repo has no other pandas dependency, and pandas pulls in numpy for
what is otherwise a simple flat-file read.

Usage: python3 import_daily_csv.py path/to/daily_export.csv
       python3 import_daily_csv.py path/to/daily_export.xlsx
"""

import csv
import os
import re
import sys
from datetime import datetime, timezone

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

_DOUBLE_URL_RE = re.compile(r"https?://.*https?://")


def _normalize_key(key: str) -> str:
    return str(key).strip().lower().replace(" ", "_").replace("-", "_")


def load_rows(path: str) -> list:
    """Returns a list of dicts with normalized lowercase_underscore keys,
    regardless of whether the source file is .csv or .xlsx."""
    if path.lower().endswith((".xlsx", ".xlsm", ".xls")):
        import openpyxl
        wb = openpyxl.load_workbook(path, data_only=True)
        ws = wb.active
        rows_iter = ws.iter_rows(values_only=True)
        header = [_normalize_key(h) for h in next(rows_iter)]
        rows = []
        for raw in rows_iter:
            if raw is None or all(v is None for v in raw):
                continue
            rows.append({header[i]: raw[i] for i in range(min(len(header), len(raw)))})
        return rows
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            return [
                {_normalize_key(k): v for k, v in row.items()}
                for row in reader
            ]


def existing_pairs() -> set:
    """Every (applywizz_id, url) already in job_queue, any status — the dedupe guard."""
    res = supabase.table("job_queue").select("applywizz_id, url").execute()
    return {(r["applywizz_id"], r["url"]) for r in (res.data or [])}


def _clean(value) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    return "" if s.lower() == "nan" else s


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 import_daily_csv.py <path-to-file.csv-or-.xlsx>")
        sys.exit(1)

    path = sys.argv[1]
    rows = load_rows(path)

    if not rows:
        print("File has no data rows.")
        return

    required = {"applywizz_id", "url", "status"}
    missing = required - set(rows[0].keys())
    if missing:
        print(f"ERROR: file is missing required column(s): {sorted(missing)}")
        print(f"Columns found: {list(rows[0].keys())}")
        sys.exit(1)

    print(f"Read {len(rows)} rows from {path}.")

    known_pairs = existing_pairs()
    print(f"{len(known_pairs)} (candidate, job) pairs already exist in job_queue.")

    imported = 0
    skipped_not_pending = 0
    skipped_duplicate = 0
    skipped_malformed = 0
    skipped_missing_data = 0

    now_iso = datetime.now(timezone.utc).isoformat()
    rows_to_insert = []

    for row in rows:
        status = _clean(row.get("status")).upper()
        applywizz_id = _clean(row.get("applywizz_id"))
        url = _clean(row.get("url"))
        client_name = _clean(row.get("client_name"))

        if status != "PENDING":
            skipped_not_pending += 1
            continue

        if not applywizz_id or not url:
            skipped_missing_data += 1
            continue

        if _DOUBLE_URL_RE.search(url):
            skipped_malformed += 1
            print(f"  ⚠️ Skipping known-malformed URL for {applywizz_id}: {url}")
            continue

        pair = (applywizz_id, url)
        if pair in known_pairs:
            skipped_duplicate += 1
            continue
        known_pairs.add(pair)  # guard against duplicates within this same file too

        rows_to_insert.append({
            "applywizz_id": applywizz_id,
            "client_name": client_name or None,
            "url": url,
            "status": "PENDING",
            "application_data": {
                "source_csv": {
                    "score": _clean(row.get("score")) or None,
                    "scored_job_id": _clean(row.get("scored_jobid")) or None,
                    "source_date": _clean(row.get("date")) or None,
                    "imported_at": now_iso,
                    "source_file": os.path.basename(path),
                }
            },
        })
        imported += 1

    if rows_to_insert:
        # Batch in chunks so one giant file doesn't send one enormous request.
        CHUNK = 200
        for i in range(0, len(rows_to_insert), CHUNK):
            supabase.table("job_queue").insert(rows_to_insert[i:i + CHUNK]).execute()

    print("\n── Import summary ──")
    print(f"  Imported:               {imported}")
    print(f"  Skipped (not PENDING):  {skipped_not_pending}")
    print(f"  Skipped (duplicate):    {skipped_duplicate}")
    print(f"  Skipped (malformed):    {skipped_malformed}")
    print(f"  Skipped (missing data): {skipped_missing_data}")
    print(f"  Total rows in file:     {len(rows)}")


if __name__ == "__main__":
    main()
