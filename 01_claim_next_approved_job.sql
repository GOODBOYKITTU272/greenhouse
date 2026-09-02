CREATE OR REPLACE FUNCTION claim_next_approved_job(worker_id TEXT)
RETURNS SETOF job_queue AS $$
  UPDATE job_queue
  SET status = 'CLAIMED',
      error_message = NULL,
      updated_at = now()
  WHERE id = (
    SELECT id
    FROM job_queue
    WHERE status = 'APPROVED'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING *;
$$ LANGUAGE sql;
