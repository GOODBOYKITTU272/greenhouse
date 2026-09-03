"""
Pick 5 real candidates for the phase-1 pilot and mark them is_pilot=true.

Only picks candidates who BOTH:
  1. Have a connected Zoho mailbox (mailbox_connected=true) — a candidate
     without one can never reach a real VERIFIED_APPLIED confirmation, which
     defeats the entire point of a pilot meant to watch that happen.
  2. Already have at least one real PENDING job in job_queue — no point
     marking someone as a pilot candidate with nothing to apply to.

Marking a candidate is_pilot=true does two things automatically, with no
other code changes needed:
  - claim_next_approved_job() (see 01_claim_next_approved_job.sql) uses a
    3-minute cooldown for pilot candidates instead of the normal 27-minute
    production pace — fast enough to actually watch the pilot's 25
    applications (5 candidates x 5 jobs) move in real time.
  - The dashboard's per-job "Approve Selected" checkboxes (not is_pilot-
    aware themselves) are how you actually cap each candidate at 5 jobs —
    review their dossier and check only 5 of their pending jobs, not
    "Approve All". is_pilot only controls pacing, not which jobs run.

This does NOT approve or submit anything by itself — it only flags which
5 candidates are in scope. You still review and approve their jobs from
the dashboard as normal.

Usage: python3 pick_pilot_candidates.py [--count 5] [--jobs-per-candidate 5]
"""

import argparse
import os

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5, help="How many candidates to pick for the pilot")
    args = parser.parse_args()

    connected = supabase.table("candidate_profiles").select("applywizz_id").eq("mailbox_connected", True).execute()
    connected_ids = [r["applywizz_id"] for r in (connected.data or [])]
    print(f"{len(connected_ids)} candidates have a connected mailbox.")

    if not connected_ids:
        print("No connected candidates found — run sync_mailbox_status.py first (or wait for the deployed worker's next 30-min cycle) so mailbox_connected is actually populated.")
        return

    picked = []
    for applywizz_id in connected_ids:
        pending = supabase.table("job_queue").select("id", count="exact").eq("applywizz_id", applywizz_id).eq("status", "PENDING").execute()
        pending_count = pending.count or 0
        if pending_count > 0:
            picked.append((applywizz_id, pending_count))
        if len(picked) >= args.count:
            break

    if not picked:
        print("No connected candidates have any PENDING jobs in job_queue right now — nothing to pilot yet.")
        return

    print(f"\nPicked {len(picked)} pilot candidates:")
    for applywizz_id, pending_count in picked:
        supabase.table("candidate_profiles").update({"is_pilot": True}).eq("applywizz_id", applywizz_id).execute()
        print(f"  {applywizz_id} — {pending_count} PENDING jobs available (review their dossier and approve at most 5)")

    print("\nDone. These candidates now get the fast 3-minute pilot pace instead of the normal 27-minute one.")
    print("Everyone else is completely unaffected — still 27 minutes as the CEO set.")


if __name__ == "__main__":
    main()
