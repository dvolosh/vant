-- BigQuery Schema for AI Insights
-- Run this script once to create the required tables in your BigQuery dataset.

-- Table 1: ai_insights
-- Stores cached AI briefings to avoid redundant Vertex AI calls (24h TTL enforced in app).
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.ai_insights` (
    generated_date DATE NOT NULL,
    audience_type STRING NOT NULL,         -- homebuyer | re_investor | reit_investor
    narrative STRING,                        -- Full AI-generated briefing text
    sentiment_score FLOAT64,              -- -1.0 (bearish) to 1.0 (bullish)
    key_themes JSON,                       -- Array of theme strings
    composite_stress_index FLOAT64,       -- CSI at time of generation (0-100)
    source_signals JSON,                  -- Snapshot of input signals used
    model_version STRING,                 -- e.g., "gemini-1.5-flash"
    generated_at TIMESTAMP,
    token_count INT64
)
PARTITION BY generated_date
OPTIONS (
    partition_expiration_days = 365,
    description = "Cached AI briefings from Vertex AI Gemini, partitioned by date. 24h cache TTL enforced at application layer."
);

-- Table 2: ai_insights_qa_log
-- Rate-limiting log for on-demand Q&A calls.
-- Application checks count(call_date = today) < MAX_QA_PER_DAY before each call.
CREATE TABLE IF NOT EXISTS `{project_id}.{dataset_id}.ai_insights_qa_log` (
    call_date DATE NOT NULL,
    called_at TIMESTAMP NOT NULL,
    audience_context STRING,             -- Audience type active when Q&A was called
    question_hash STRING,               -- SHA256 of question (no PII stored)
    response_length INT64,              -- Characters in response
    token_count INT64,
    session_id STRING                   -- Random per-session UUID (no user identity)
)
PARTITION BY call_date
OPTIONS (
    partition_expiration_days = 90,
    description = "Rate-limiting log for on-demand Q&A. Query count(call_date = CURRENT_DATE()) to enforce daily cap."
);
