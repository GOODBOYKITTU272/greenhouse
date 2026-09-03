"""
Pick 5 real candidates for the phase-1 pilot and mark them is_pilot=true.

Only requirement: the candidate has at least one real PENDING job in
job_queue — no point marking someone as a pilot candidate with nothing to
apply to. A connected Zoho mailbox is NOT required to be picked — that only
matters later, when a job actually reaches the point of checking for a real
OTP/confirmation email. claim_next_approved_job() already treats
mailbox_connected as a claim-order preference, not a hard gate (see
01_claim_next_approved_job.sql), so picking ahead of the mailbox sync is
safe — just check the dashboard's mailbox status before relying on a
pilot candidate's confirmation step.

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
candidates are in scope. You still review and approve their jobs from
the dashboard as normal.

Usage: python3 pick_pilot_candidates.py [--count 5]
"""

import argparse
import os

from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def mark_pilot(applywizz_id):
    """
    Set is_pilot=true for a candidate. Most candidates already have a
    candidate_profiles row by the time this runs (brain_worker creates one
    the first time it processes any of their jobs) — update() handles that
    case. If brain_worker hasn't reached them yet, update() silently
    matches nothing, so fall back to inserting a placeholder row: brain_worker's
    own upsert() never sends the is_pilot column, so it can't clobber this
    later when it fills in the real profile_json.
    """
    resp = supabase.table("candidate_profiles").update({"is_pilot": True}).eq("applywizz_id", applywizz_id).execute()
    if resp.data:
        return "updated existing"
    supabase.table("candidate_profiles").insert({
        "applywizz_id": applywizz_id,
        "profile_json": {},
        "is_pilot": True,
    }).execute()
    return "inserted placeholder"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=5, help="How many candidates to pick for the pilot")
    args = parser.parse_args()

    pending = supabase.table("job_queue").select("applywizz_id").eq("status", "PENDING").execute()
    rows = pending.data or []
    if not rows:
        print("No PENDING jobs in job_queue right now — nothing to pilot yet.")
        return

    counts = {}
    order = []
    for r in rows:
        applywizz_id = r["applywizz_id"]
        if applywizz_id not in counts:
            counts[applywizz_id] = 0
            order.append(applywizz_id)
        counts[applywizz_id] += 1

    picked = order[:args.count]
    print(f"\nPicked {len(picked)} pilot candidates:")
    for applywizz_id in picked:
        outcome = mark_pilot(applywizz_id)
        print(f"  {applywizz_id} — {counts[applywizz_id]} PENDING jobs available ({outcome}) — review their dossier and approve at most 5")

    print("\nDone. These candidates now get the fast 3-minute pilot pace instead of the normal 27-minute one.")
    print("Everyone else is completely unaffected — still 27 minutes as the CEO set.")
    print("Mailbox connection wasn't checked to pick them — before trusting a pilot candidate's confirmation step, check the dashboard shows their mailbox as connected.")


if __name__ == "__main__":
    main()
