-- =============================================================
-- FILE: migrations/001_init_schema.sql
-- PURPOSE: Create all tables for the Talent Pool Search app.
--          Run once in Supabase SQL editor before starting backend.
--
-- Tables:
--   candidates       → one row per uploaded resume (contact + AI results)
--   skills           → deduplicated skill names
--   candidate_skills → many-to-many join between candidates and skills
--   resumes          → raw/scrubbed text + S3 URL + processing status
--   upload_jobs      → tracks a batch upload so frontend can poll progress
-- =============================================================

-- Clean slate (safe to re-run in dev)
DROP TABLE IF EXISTS candidate_skills CASCADE;
DROP TABLE IF EXISTS skills CASCADE;
DROP TABLE IF EXISTS resumes CASCADE;
DROP TABLE IF EXISTS candidates CASCADE;
DROP TABLE IF EXISTS upload_jobs CASCADE;

-- ----------------------------------------------------------------
-- upload_jobs: one row per POST /upload request (batch of files)
-- ----------------------------------------------------------------
CREATE TABLE upload_jobs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    total_files     INT NOT NULL DEFAULT 0,
    processed_files INT NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT 'pending'  -- pending | processing | completed | failed
                    CHECK (status IN ('pending','processing','completed','failed')),
    error_message   TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
-- candidates: core record created after AI parsing completes
-- ----------------------------------------------------------------
CREATE TABLE candidates (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    -- Contact details extracted via regex BEFORE PII scrubbing
    name              TEXT,
    email             TEXT,
    phone             TEXT,
    linkedin_url      TEXT,

    -- AI-extracted fields from scrubbed text
    location          TEXT,
    years_experience  NUMERIC(4,1),   -- e.g. 4.5 years
    current_title     TEXT,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
-- skills: normalized skill names (lowercased)
-- ----------------------------------------------------------------
CREATE TABLE skills (
    id    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name  TEXT UNIQUE NOT NULL   -- e.g. "python", "react", "project management"
);

-- ----------------------------------------------------------------
-- candidate_skills: links candidates to their skills (many-to-many)
-- ----------------------------------------------------------------
CREATE TABLE candidate_skills (
    candidate_id  UUID NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    skill_id      UUID NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (candidate_id, skill_id)
);

-- ----------------------------------------------------------------
-- resumes: stores the original file reference + extracted text
-- ----------------------------------------------------------------
CREATE TABLE resumes (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_id      UUID REFERENCES candidates(id) ON DELETE CASCADE,
    upload_job_id     UUID NOT NULL REFERENCES upload_jobs(id) ON DELETE CASCADE,

    original_filename TEXT NOT NULL,
    s3_url            TEXT,           -- URL to original file in S3

    raw_text          TEXT,           -- text extracted from PDF/DOCX
    scrubbed_text     TEXT,           -- raw_text after PII replacement
    content_hash      TEXT,           -- sha256 of scrubbed_text (for dedup)

    processing_status TEXT NOT NULL DEFAULT 'pending'
                      -- 'duplicate' = identical resume already in the pool
                      CHECK (processing_status IN ('pending','processing','completed','failed','duplicate')),
    error_message     TEXT,

    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ----------------------------------------------------------------
-- Indexes for common query patterns
-- ----------------------------------------------------------------

-- Search by location (ILIKE)
CREATE INDEX idx_candidates_location ON candidates (location);

-- Filter by years_experience
CREATE INDEX idx_candidates_years ON candidates (years_experience);

-- Skills join lookups
CREATE INDEX idx_candidate_skills_candidate ON candidate_skills (candidate_id);
CREATE INDEX idx_candidate_skills_skill     ON candidate_skills (skill_id);

-- Skill name search (case-insensitive)
CREATE INDEX idx_skills_name ON skills (name);

-- Job polling
CREATE INDEX idx_resumes_upload_job ON resumes (upload_job_id);

-- Deduplication lookups (find resume by content hash)
CREATE INDEX idx_resumes_content_hash ON resumes (content_hash);
