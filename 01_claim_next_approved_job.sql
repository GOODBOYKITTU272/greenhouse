-- Run the ALTER below once (idempotent) before replacing the function, so the
-- column it references already exists on a fresh project too:
--
--   ALTER TABLE candidate_profiles
--     ADD COLUMN IF NOT EXISTS mailbox_connected BOOLEAN NOT NULL DEFAULT false,
--     ADD COLUMN IF NOT EXISTS mailbox_synced_at TIMESTAMPTZ;
--
-- mailbox_connected is kept in sync by sync_mailbox_status.py against the
-- real ZOHO_MAIL_READER connected-mailbox list, run on a schedule (Railway
-- cron or similar) — it is NOT computed live inside this function, since a
-- SQL claim query can't make an HTTP call.
--
-- Priority: among every APPROVED job, a candidate with a connected mailbox
-- is claimed before one without, oldest-first within each group. A
-- candidate without a connected mailbox can never reach a verified status
-- (no way to read the OTP/confirmation email), so there's no reason to burn
-- a claim slot on them ahead of someone who actually can. Non-connected
-- candidates are NOT blocked — they still get claimed and processed, just
-- after the connected ones when both are waiting.
CREATE OR REPLACE FUNCTION claim_next_approved_job(worker_id TEXT)
RETURNS SETOF job_queue AS $$
  UPDATE job_queue
  SET status = 'CLAIMED',
      error_message = NULL,
      updated_at = now()
  WHERE id = (
    SELECT jq.id
    FROM job_queue jq
    LEFT JOIN candidate_profiles cp ON cp.applywizz_id = jq.applywizz_id
    WHERE jq.status = 'APPROVED'
    ORDER BY COALESCE(cp.mailbox_connected, false) DESC, jq.created_at ASC
    LIMIT 1
    FOR UPDATE OF jq SKIP LOCKED
  )
  RETURNING *;
$$ LANGUAGE sql;
