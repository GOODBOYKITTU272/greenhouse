-- ApplyWizz Database Schema
--
-- Reconstructed from what brain_worker.py / muscle_worker.py / applywizz_brain.py /
-- dashboard/src/App.jsx actually read and write in production. The previous version of
-- this file described a `clients` / `job_applications` schema that nothing in the real
-- pipeline has ever used — that draft was abandoned early and left behind by mistake.
--
-- This file is a reference, not a guaranteed match for the live database: run it against
-- a fresh project, or diff it against `information_schema.columns` on the real one, before
-- trusting it as authoritative. Columns marked "inferred" are read/written dynamically
-- (e.g. via JSONB blobs) and may not be exhaustive.

-- ── job_queue ──────────────────────────────────────────────────────────────
-- One row per (candidate, job) pair. Written by brain_worker.py (PENDING → NEEDS_REVIEW
-- or ERROR), read/updated by the dashboard (NEEDS_REVIEW → APPROVED), and driven through
-- the rest of its lifecycle by muscle_worker.py (APPROVED → CLAIMED → FILLING →
-- SUBMITTED_EMAIL_PENDING → VERIFIED_APPLIED, or ERROR / OTP_TIMEOUT / VALIDATION_FAILED).
CREATE TABLE IF NOT EXISTS job_queue (
    id                    BIGSERIAL PRIMARY KEY,
    applywizz_id          TEXT NOT NULL,
    client_name           TEXT,
    url                   TEXT NOT NULL,
    status                TEXT NOT NULL DEFAULT 'PENDING',
    application_data      JSONB,              -- brain_worker's full answer_map + metadata
    approved_answer_map   JSONB,              -- real per-job telemetry captured by muscle_worker
                                               -- ({started_at, time_taken, email}) once VERIFIED_APPLIED;
                                               -- never populate this with placeholder/templated values
    error_message         TEXT,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_job_queue_status       ON job_queue(status);
CREATE INDEX IF NOT EXISTS idx_job_queue_applywizz_id ON job_queue(applywizz_id);
CREATE INDEX IF NOT EXISTS idx_job_queue_url          ON job_queue(url);

-- ── job_schemas ────────────────────────────────────────────────────────────
-- One row per unique job posting (keyed by canonical_url, tracking params stripped).
-- Populated once via Greenhouse's public boards-api.greenhouse.io ?questions=true GET,
-- then reused by every candidate who applies to that same posting — this is the
-- schema-dedup cache described in brain_worker.py's get_or_cache_job_schema().
CREATE TABLE IF NOT EXISTS job_schemas (
    canonical_url   TEXT PRIMARY KEY,
    raw_url         TEXT,
    board_token     TEXT,
    job_id          TEXT,
    job_title       TEXT,
    question_count  INTEGER,
    job_data        JSONB NOT NULL,   -- raw Greenhouse job payload (questions, demographic_questions, compliance, etc.)
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── candidate_profiles ─────────────────────────────────────────────────────
-- One row per candidate. Cached once from the CRM (apply-wizz.me/api/get-client-details)
-- by brain_worker.py's get_or_cache_candidate() so repeat lookups don't re-hit the CRM API.
CREATE TABLE IF NOT EXISTS candidate_profiles (
    applywizz_id   TEXT PRIMARY KEY,
    profile_json   JSONB NOT NULL,   -- raw CRM response: {client: {...}, additional_information: {...}}
    resume_text    TEXT,             -- extracted PDF text, used by the AI answer layer
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── ai_memory_bank ─────────────────────────────────────────────────────────
-- Per-candidate cache of previously-approved answers, keyed by (applywizz_id, question_label),
-- so the same candidate's same question is never re-resolved from scratch. NOT shared across
-- candidates — different people can have different correct answers to an identically-worded
-- question (this is intentional; do not "optimize" it into a cross-candidate cache).
CREATE TABLE IF NOT EXISTS ai_memory_bank (
    applywizz_id    TEXT NOT NULL,
    question_label  TEXT NOT NULL,
    answer          TEXT,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (applywizz_id, question_label)
);

-- ── Row Level Security ─────────────────────────────────────────────────────
-- All four tables above should have RLS enabled with no permissive anon policy: the
-- dashboard's anon key is used client-side (visible in the deployed JS bundle), and every
-- one of these tables holds PII (candidate address/DOB/race/disability/veteran status) or
-- lets a caller flip a job to APPROVED. Service-role access (used by brain_worker.py /
-- muscle_worker.py) bypasses RLS by design; that's fine, that key never leaves the server.
--
-- Verify this is actually true in the live project — RLS state isn't visible from this repo:
--   select relname, relrowsecurity from pg_class
--   where relname in ('job_queue','job_schemas','candidate_profiles','ai_memory_bank');
