-- ============================================================================
-- Migration: 017_fts5_index.sql
-- Purpose: Create FTS5 virtual table for full-text search on posts
-- Author: Super-Passport Search Phase 1
-- Date: 2026-03-11
-- ============================================================================

-- Drop existing FTS5 table and triggers if they exist (for re-runnable migrations)
DROP TABLE IF EXISTS posts_fts;
DROP TRIGGER IF EXISTS posts_fts_insert;
DROP TRIGGER IF EXISTS posts_fts_update;
DROP TRIGGER IF EXISTS posts_fts_delete;

-- ============================================================================
-- 1. Create FTS5 Virtual Table
-- ============================================================================
-- Standalone FTS5 table (not using external content)
-- Using 'unicode61' tokenizer for better Unicode support (Russian text)
CREATE VIRTUAL TABLE posts_fts USING fts5(
    message_text,
    tokenize='unicode61'
);

-- ============================================================================
-- 2. Create Triggers for Automatic Sync
-- ============================================================================
-- These triggers keep FTS5 index in sync with posts table for ALL write paths:
-- - add_expert.py (ORM)
-- - channel_syncer (ORM)
-- - import_video_json.py (raw SQLite)
-- - update_production_db.sh (bulk replace)

-- Trigger: Sync on INSERT (only posts with >30 chars)
CREATE TRIGGER posts_fts_insert AFTER INSERT ON posts
WHEN LENGTH(COALESCE(new.message_text, '')) > 30
BEGIN
    INSERT INTO posts_fts(rowid, message_text)
    VALUES (new.post_id, new.message_text);
END;

-- Trigger: Sync on UPDATE of message_text
-- IMPORTANT: Always delete old entry, then conditionally insert new one
CREATE TRIGGER posts_fts_update AFTER UPDATE OF message_text ON posts
BEGIN
    -- Always delete old entry (handles case when post shrinks to <=30 chars)
    DELETE FROM posts_fts WHERE rowid = old.post_id;
    -- Only insert new entry if it's >30 chars
    INSERT INTO posts_fts(rowid, message_text)
    SELECT new.post_id, new.message_text
    WHERE LENGTH(COALESCE(new.message_text, '')) > 30;
END;

-- Trigger: Sync on DELETE
CREATE TRIGGER posts_fts_delete AFTER DELETE ON posts
BEGIN
    DELETE FROM posts_fts WHERE rowid = old.post_id;
END;

-- ============================================================================
-- 3. Backfill Existing Data
-- ============================================================================
-- Only index posts with meaningful text content (>30 characters)
-- This matches the media-only filter in simplified_query_endpoint.py

INSERT INTO posts_fts(rowid, message_text)
SELECT post_id, COALESCE(message_text, '')
FROM posts
WHERE LENGTH(COALESCE(message_text, '')) > 30;

-- ============================================================================
-- 4. Verification
-- ============================================================================
-- Run these queries to verify the migration:
-- SELECT COUNT(*) FROM posts_fts;  -- Should be ~5145 (FTS-eligible posts)
-- SELECT * FROM posts_fts WHERE posts_fts MATCH 'kubernetes' LIMIT 5;
-- SELECT * FROM posts_fts WHERE posts_fts MATCH 'кубер*' LIMIT 5;
