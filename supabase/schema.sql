-- ==============================================================================
-- SovereignPrivacy AI — Supabase PostgreSQL Schema
-- ==============================================================================
-- Run this script in the Supabase SQL Editor (Dashboard -> SQL Editor -> New Query)
-- to create all necessary tables, indexes, and Row Level Security policies.
-- ==============================================================================

-- 1. Users & Core Profiles
CREATE TABLE IF NOT EXISTS public.users (
    id            TEXT PRIMARY KEY,
    name          TEXT,
    email         TEXT,
    phone         TEXT,
    pan           TEXT,
    city          TEXT,
    country       TEXT DEFAULT 'IN',
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Identified Digital Identities & Handles
CREATE TABLE IF NOT EXISTS public.identities (
    id          TEXT PRIMARY KEY,
    user_id     TEXT REFERENCES public.users(id) ON DELETE CASCADE,
    alias       TEXT NOT NULL,
    alias_type  TEXT NOT NULL,
    confidence  REAL DEFAULT 1.0,
    rationale   TEXT DEFAULT '',
    created_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Agent Runs & Audits
CREATE TABLE IF NOT EXISTS public.runs (
    id          TEXT PRIMARY KEY,
    user_id     TEXT REFERENCES public.users(id) ON DELETE CASCADE,
    started_at  TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    mode        TEXT,   -- llm | deterministic
    model       TEXT,
    risk_before REAL,
    risk_after  REAL,
    summary     TEXT
);

-- 4. Confirmed Data Exposures (Breaches, Stealers, Pastes, Open Web)
CREATE TABLE IF NOT EXISTS public.exposures (
    id               TEXT PRIMARY KEY,
    user_id          TEXT REFERENCES public.users(id) ON DELETE CASCADE,
    run_id           TEXT,
    source_type      TEXT NOT NULL,   -- breach | data_broker | paste | public_profile | open_web
    source_name      TEXT NOT NULL,
    source_id        TEXT NOT NULL,   -- broker slug / breach name
    record_id        TEXT,
    data_found       JSONB DEFAULT '[]'::jsonb,
    detail           JSONB DEFAULT '{}'::jsonb,
    match_confidence REAL DEFAULT 1.0,
    match_tier       TEXT DEFAULT 'definite',
    evidence_class   TEXT DEFAULT 'verified',
    evidence         JSONB DEFAULT '[]'::jsonb,
    risk_score       REAL DEFAULT 0.0,
    severity         TEXT DEFAULT 'medium',
    status           TEXT DEFAULT 'exposed', -- exposed | requested | acknowledged | removed | reappeared
    discovered_at    TIMESTAMPTZ DEFAULT NOW(),
    removed_at       TIMESTAMPTZ,
    verified_at      TIMESTAMPTZ
);

-- 5. Statutory Erasure & Right-to-be-Forgotten Notices (DPDP 2023 / GDPR)
CREATE TABLE IF NOT EXISTS public.requests (
    id              TEXT PRIMARY KEY,
    user_id         TEXT REFERENCES public.users(id) ON DELETE CASCADE,
    exposure_id     TEXT REFERENCES public.exposures(id) ON DELETE SET NULL,
    jurisdiction    TEXT DEFAULT 'dpdp',
    statute         TEXT,
    legal_basis     TEXT,
    request_text    TEXT,
    reference_id    TEXT,
    receipt_hash    TEXT,
    status          TEXT DEFAULT 'drafted', -- drafted | awaiting_approval | submitted | acknowledged | completed | rejected | overdue | escalated
    confirmation_id TEXT,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    submitted_at    TIMESTAMPTZ,
    deadline        TIMESTAMPTZ,
    deadline_days   INTEGER DEFAULT 30,
    last_followup   TIMESTAMPTZ,
    followup_count  INTEGER DEFAULT 0
);

-- 6. Live Agent Events & Reasoning Step Feed
CREATE TABLE IF NOT EXISTS public.agent_events (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT,
    run_id      TEXT,
    ts          TIMESTAMPTZ DEFAULT NOW(),
    agent       TEXT,   -- identity | discovery | risk | legal | action | followup | verification | orchestrator
    phase       TEXT,
    message     TEXT,
    tool_name   TEXT,
    tool_input  TEXT,
    tool_output TEXT,
    status      TEXT    -- running | ok | error | awaiting_approval
);

-- 7. Cryptographic Audit Hash Chain Receipts
CREATE TABLE IF NOT EXISTS public.audit_receipts (
    seq           BIGSERIAL PRIMARY KEY,
    receipt_id    TEXT,
    timestamp     TIMESTAMPTZ DEFAULT NOW(),
    action        TEXT NOT NULL,
    details       JSONB DEFAULT '{}'::jsonb,
    previous_hash TEXT NOT NULL,
    hash          TEXT NOT NULL
);

-- ─── INDEXES ──────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS idx_exposures_user ON public.exposures(user_id);
CREATE INDEX IF NOT EXISTS idx_exposures_status ON public.exposures(status);
CREATE INDEX IF NOT EXISTS idx_events_run ON public.agent_events(run_id);
CREATE INDEX IF NOT EXISTS idx_events_user ON public.agent_events(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_user ON public.requests(user_id);
CREATE INDEX IF NOT EXISTS idx_requests_status ON public.requests(status);
CREATE INDEX IF NOT EXISTS idx_audit_seq ON public.audit_receipts(seq);

-- ─── ROW LEVEL SECURITY (RLS) POLICIES ────────────────────────────────────────
-- Enable RLS on all tables
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.exposures ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.agent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.audit_receipts ENABLE ROW LEVEL SECURITY;

-- Allow public read/write access via API (suitable for hackathon demo & anon key)
-- For production, scope to auth.uid() = user_id
CREATE POLICY "Public full access on users" ON public.users FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public full access on identities" ON public.identities FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public full access on runs" ON public.runs FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public full access on exposures" ON public.exposures FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public full access on requests" ON public.requests FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public full access on agent_events" ON public.agent_events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Public full access on audit_receipts" ON public.audit_receipts FOR ALL USING (true) WITH CHECK (true);

-- Enable Realtime broadcasting on agent_events and exposures
ALTER PUBLICATION supabase_realtime ADD TABLE public.agent_events;
ALTER PUBLICATION supabase_realtime ADD TABLE public.exposures;
