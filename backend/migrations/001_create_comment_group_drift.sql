-- Migration: Create comment_group_drift table
-- Purpose: Store pre-analyzed drift topics for comment groups
-- Date: 2025-10-06

CREATE TABLE IF NOT EXISTS comment_group_drift (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- Link to anchor post
    post_id INTEGER NOT NULL,

    -- Drift analysis
    has_drift BOOLEAN NOT NULL DEFAULT FALSE,
    drift_topics TEXT,  -- JSON array of drift topic objects

    -- Metadata
    analyzed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    analyzed_by TEXT NOT NULL,  -- e.g. 'sonnet-4.5'

    -- Foreign key
    FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE,

    -- Indexes
    UNIQUE(post_id)
);

-- Index for quick lookup of drift groups
CREATE INDEX IF NOT EXISTS idx_drift_has_drift ON comment_group_drift(has_drift);

-- Index for filtering by analysis date
CREATE INDEX IF NOT EXISTS idx_drift_analyzed_at ON comment_group_drift(analyzed_at);

-- Example drift_topics JSON structure:
-- [
--   {
--     "topic": "Стек для разработки AI-агентов",
--     "keywords": ["TypeScript", "Python", "Vercel AI SDK"],
--     "key_phrases": ["какой стек используешь"],
--     "context": "Вопрос о технологическом стеке"
--   }
-- ]
