-- ApplyWizz Database Schema
-- This script sets up the PostgreSQL database schema for the ApplyWizz job application pipeline.

-- 1. Status Enum
-- Defines the various states a job application can be in during its lifecycle.
CREATE TYPE application_status AS ENUM (
    'pending_extraction',
    'pending_fuzzy',
    'pending_ai',
    'ready_to_apply',
    'processing',
    'success',
    'failed_captcha',
    'failed_validation'
);

-- 7. clients Table (minimal)
-- Stores information about the clients (users) applying for jobs.
CREATE TABLE clients (
    id UUID PRIMARY KEY,
    email TEXT UNIQUE NOT NULL,
    full_name TEXT,
    visa_status TEXT,
    phone TEXT,
    linkedin TEXT,
    resume_s3_url TEXT,
    default_answers JSONB,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- 2. job_applications Table
-- Core table storing each job application and its current state.
CREATE TABLE job_applications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_id UUID NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    job_url TEXT NOT NULL,
    board_token TEXT NOT NULL,
    job_id TEXT NOT NULL,
    job_title TEXT,
    company_name TEXT,
    status application_status DEFAULT 'pending_extraction',
    answer_map JSONB,
    resume_s3_url TEXT,
    ai_questions_count INTEGER DEFAULT 0,
    browserless_session_id TEXT,
    confirmation_url TEXT,
    error_message TEXT,
    retry_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    executed_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE (client_id, job_url)
);

-- 3. Indexes
-- Index on status for the Muscle worker to quickly find ready_to_apply rows
CREATE INDEX idx_job_applications_status ON job_applications(status);
-- Index on client_id for dashboard queries
CREATE INDEX idx_job_applications_client_id ON job_applications(client_id);
-- Index on created_at for time-based queries
CREATE INDEX idx_job_applications_created_at ON job_applications(created_at);

-- 5. Auto-update updated_at trigger
-- Function to update the updated_at column to the current time
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger to execute the function on any row update
CREATE TRIGGER update_job_applications_modtime
BEFORE UPDATE ON job_applications
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- 4. RPC Function: claim_next_job
-- Concurrency-safe function for the Muscle worker to atomically grab the next job
CREATE OR REPLACE FUNCTION claim_next_job(worker_id TEXT)
RETURNS SETOF job_applications AS $$
  UPDATE job_applications
  SET status = 'processing',
      browserless_session_id = worker_id,
      updated_at = now()
  WHERE id = (
    SELECT id FROM job_applications
    WHERE status = 'ready_to_apply'
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  RETURNING *;
$$ LANGUAGE sql;

-- 6. Row Level Security (RLS)
-- Enable RLS on the job_applications table
ALTER TABLE job_applications ENABLE ROW LEVEL SECURITY;

-- Clients can only SELECT their own rows
CREATE POLICY select_own_applications 
ON job_applications FOR SELECT 
USING (client_id = auth.uid());

-- Note: Service role inherently bypasses RLS in Supabase. Backend workers using the service_role key will have full access.
