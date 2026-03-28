-- ============================================================================
-- Migration: 023_fts5_remove_metadata.sql
-- Purpose: Remove post_metadata keywords from FTS5 index and triggers.
--          AI Scout v3 + Vector KNN make LLM-generated metadata redundant.
--          FTS5 content now uses message_text only (no json_extract).
-- Date: 2026-03-28
-- Idempotent: Safe to run multiple times (DROP IF EXISTS).
-- ============================================================================

-- Drop existing FTS5 table and triggers
DROP TABLE IF EXISTS posts_fts;
DROP TRIGGER IF EXISTS posts_fts_insert;
DROP TRIGGER IF EXISTS posts_fts_update;
DROP TRIGGER IF EXISTS posts_fts_delete;

-- Drop metadata-related index (from migration 018)
DROP INDEX IF EXISTS idx_posts_post_metadata_null;

-- ============================================================================
-- 1. Create FTS5 Virtual Table (same structure, cleaner content)
-- ============================================================================
CREATE VIRTUAL TABLE posts_fts USING fts5(
    content,
    expert_id UNINDEXED,
    created_at UNINDEXED,
    tokenize='unicode61'
);

-- ============================================================================
-- 2. Populate FTS5 with message_text only (no metadata keywords)
-- ============================================================================
INSERT INTO posts_fts(rowid, content, expert_id, created_at)
SELECT
    post_id,
    message_text,
    expert_id,
    created_at
FROM posts
WHERE message_text IS NOT NULL AND LENGTH(message_text) > 30;

-- ============================================================================
-- 3. Create Triggers for Automatic Sync
-- ============================================================================
CREATE TRIGGER posts_fts_insert AFTER INSERT ON posts
WHEN LENGTH(COALESCE(new.message_text, '')) > 30
BEGIN
    INSERT INTO posts_fts(rowid, content, expert_id, created_at)
    VALUES (new.post_id, new.message_text, new.expert_id, new.created_at);
END;

CREATE TRIGGER posts_fts_update AFTER UPDATE OF message_text ON posts
WHEN LENGTH(COALESCE(new.message_text, '')) > 30
BEGIN
    DELETE FROM posts_fts WHERE rowid = old.post_id;
    INSERT INTO posts_fts(rowid, content, expert_id, created_at)
    VALUES (new.post_id, new.message_text, new.expert_id, new.created_at);
END;

CREATE TRIGGER posts_fts_delete AFTER DELETE ON posts
BEGIN
    DELETE FROM posts_fts WHERE rowid = old.post_id;
END;
