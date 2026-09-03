-- Run the ALTER below once (idempotent) before replacing the function, so the
-- columns it references already exist on a fresh project too:
--
--   ALTER TABLE candidate_profiles
--     ADD COLUMN IF NOT EXISTS mailbox_connected BOOLEAN NOT NULL DEFAULT false,
--     ADD COLUMN IF NOT EXISTS mailbox_synced_at TIMESTAMPTZ,
--     ADD COLUMN IF NOT EXISTS is_pilot BOOLEAN NOT NULL DEFAULT false;
--
-- mailbox_connected is kept in sync by sync_mailbox_status.py against the
-- real ZOHO_MAIL_READER connected-mailbox list, run on a schedule (already
-- wired into muscle_worker.py's own loop — see maybe_sync_mailbox_status())
-- — it is NOT computed live inside this function, since a SQL claim query
-- can't make an HTTP call. is_pilot is set by pick_pilot_candidates.py for
-- exactly the phase-1 pilot candidates — everyone else defaults to false.
--
-- Claim priority, in order:
--   1. A candidate with a connected mailbox is claimed before one without —
--      a candidate with no connected mailbox can never reach a verified
--      status (no way to read the OTP/confirmation email), so there's no
--      reason to burn a claim slot on them ahead of someone who actually can.
--   2. PER-CANDIDATE PACING: never claim a new job for a candidate who had
--      any job move past APPROVED (claimed/filled/submitted/etc.) recently —
--      27 minutes for everyone (confirmed production business rule), except
--      3 minutes for candidates flagged is_pilot=true — the phase-1 pilot's
--      deliberately faster pace to actually observe a handful of real
--      applications complete quickly, reverting to 27 minutes for them too
--      once the pilot ends and is_pilot is cleared. A candidate currently in
--      cooldown is simply skipped this cycle; their other APPROVED jobs wait.
--   3. Within everyone actually eligible, the highest-scored job wins —
--      score comes from import_daily_csv.py's
--      application_data->'source_csv'->>'score', so "apply to the
--      candidate's best match first" happens automatically with zero
--      extra bookkeeping.
--   4. Oldest first as the final tiebreaker.
--
-- Non-connected candidates are NOT blocked entirely — they still get
-- claimed and processed, just after connected ones when both are waiting.
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
      AND NOT EXISTS (
        SELECT 1
        FROM job_queue recent
        WHERE recent.applywizz_id = jq.applywizz_id
          AND recent.status NOT IN ('PENDING', 'NEEDS_REVIEW', 'APPROVED')
          AND recent.updated_at > now() - (
            CASE WHEN COALESCE(cp.is_pilot, false)
              THEN interval '3 minutes'
              ELSE interval '27 minutes'
            END
          )
      )
    ORDER BY
      COALESCE(cp.mailbox_connected, false) DESC,
      -- A single row with a non-numeric/blank score must never break claiming
      -- for every other row too — a raw ::numeric cast errors hard on bad
      -- input and Postgres evaluates ORDER BY across the whole result set,
      -- so one bad value would take down the entire claim query.
      COALESCE(
        (CASE
          WHEN (jq.application_data -> 'source_csv' ->> 'score') ~ '^-?[0-9]+(\.[0-9]+)?$'
          THEN (jq.application_data -> 'source_csv' ->> 'score')::numeric
          ELSE NULL
        END),
        -1
      ) DESC,
      jq.created_at ASC
    LIMIT 1
    FOR UPDATE OF jq SKIP LOCKED
  )
  RETURNING *;
$$ LANGUAGE sql;
