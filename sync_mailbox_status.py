"""
Sync mailbox connectivity status from ZOHO_MAIL_READER into candidate_profiles.

Calls ZOHO_MAIL_READER's real GET /api/zoho/mailboxes endpoint (confirmed
against its actual source in this repo, ZOHO_MAIL_READER/src/routes/
zoho.routes.ts — NOT "/api/zoho/ui/users", which was an earlier guess this
session made without checking the real source and turned out not to exist).
Marks candidate_profiles.mailbox_connected = true for every candidate whose
stored email matches an "active" connected mailbox.

This has to run as a periodic job, not inline in muscle_worker's claim loop —
hitting Zoho on every single claim would be slow and pointless when mailbox
connections change rarely. Run this on a schedule (Railway cron, every
15-30 min is plenty) and claim_next_approved_job() reads the column it
writes to prioritize mailbox-connected candidates.

This sandbox has no network path to ZOHO_MAIL_READER (confirmed: the
egress proxy 403s the CONNECT to zoho-mail-reader.onrender.com), so this
script has not been run here — run it from Railway or your own machine,
where it has real network access, and check its printed summary.

Usage: python3 sync_mailbox_status.py
"""

import os
from datetime import datetime, timezone

import requests
from supabase import create_client

SUPABASE_URL = os.environ["SUPABASE_URL"]
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
ZOHO_READER_BASE = os.environ.get("ZOHO_BASE_URL", "https://zoho-mail-reader.onrender.com").rstrip("/")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)


def fetch_connected_emails() -> set:
    resp = requests.get(f"{ZOHO_READER_BASE}/api/zoho/mailboxes", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    mailboxes = data.get("mailboxes") or []
    return {
        m["email"].strip().lower()
        for m in mailboxes
        if m.get("email") and m.get("status", "active") == "active"
    }


def candidate_emails(profile_json: dict) -> set:
    client = (profile_json or {}).get("client", {})
    emails = {
        str(client.get("company_email") or "").strip().lower(),
        str(client.get("personal_email") or "").strip().lower(),
    }
    emails.discard("")
    return emails


def sync():
    connected_emails = fetch_connected_emails()
    print(f"ZOHO_MAIL_READER reports {len(connected_emails)} active connected mailboxes.")

    res = supabase.table("candidate_profiles").select("applywizz_id, profile_json, mailbox_connected").execute()
    profiles = res.data or []
    print(f"Checking {len(profiles)} candidate_profiles rows...")

    now_iso = datetime.now(timezone.utc).isoformat()
    updated = 0
    newly_connected = 0
    for p in profiles:
        is_connected = bool(candidate_emails(p.get("profile_json") or {}) & connected_emails)
        was_connected = bool(p.get("mailbox_connected"))

        if is_connected != was_connected:
            supabase.table("candidate_profiles").update({
                "mailbox_connected": is_connected,
                "mailbox_synced_at": now_iso,
            }).eq("applywizz_id", p["applywizz_id"]).execute()
            updated += 1
            if is_connected and not was_connected:
                newly_connected += 1
        else:
            # Still touch the timestamp so "last synced" is meaningful even
            # when nothing changed for this candidate.
            supabase.table("candidate_profiles").update({
                "mailbox_synced_at": now_iso,
            }).eq("applywizz_id", p["applywizz_id"]).execute()

    connected_total = sum(1 for p in profiles if candidate_emails(p.get("profile_json") or {}) & connected_emails)
    pct = (connected_total / len(profiles) * 100) if profiles else 0.0
    print(f"Done. {connected_total}/{len(profiles)} candidates have a connected mailbox ({pct:.1f}%).")
    print(f"{updated} rows changed this run ({newly_connected} newly connected).")


if __name__ == "__main__":
    sync()
