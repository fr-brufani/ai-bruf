-- ══════════════════════════════════════════════
-- AI BRUF Bot — Schema Supabase
-- Incolla nel SQL Editor di Supabase ed esegui
-- ══════════════════════════════════════════════

-- 1. Memoria persistente dell'agente (sostituisce memory.md)
CREATE TABLE IF NOT EXISTS agent_memory (
    id      INTEGER PRIMARY KEY DEFAULT 1,
    content TEXT NOT NULL DEFAULT '',
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
INSERT INTO agent_memory (id, content) VALUES (1, '') ON CONFLICT (id) DO NOTHING;

-- 2. Cronologia conversazione (scambi puliti user↔assistant)
CREATE TABLE IF NOT EXISTS conversation_messages (
    id         BIGSERIAL PRIMARY KEY,
    role       TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content    TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 3. Job applications tracker
CREATE TABLE IF NOT EXISTS job_applications (
    id          BIGSERIAL PRIMARY KEY,
    company     TEXT NOT NULL,
    role_title  TEXT,
    url         TEXT,
    cv_type     TEXT DEFAULT 'sales',
    status      TEXT DEFAULT 'applied'
                     CHECK (status IN ('applied','interviewing','offer','rejected','withdrawn')),
    notes       TEXT,
    applied_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Analisi spese Revolut mensili
CREATE TABLE IF NOT EXISTS expense_reports (
    id            BIGSERIAL PRIMARY KEY,
    period        TEXT NOT NULL UNIQUE,   -- formato 'YYYY-MM' es. '2026-05'
    csv_raw       TEXT,
    analysis_text TEXT,
    total_spent   NUMERIC(10,2),
    created_at    TIMESTAMPTZ DEFAULT NOW()
);
