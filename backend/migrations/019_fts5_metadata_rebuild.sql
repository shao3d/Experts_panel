-- ============================================================================
-- Migration: 019_fts5_metadata_rebuild.sql
-- Purpose: Rebuild FTS5 index with metadata keywords support
-- Author: Scout Level 2 Upgrade
-- Date: 2026-03-14
-- ============================================================================

-- Drop existing FTS5 table and triggers
DROP TABLE IF EXISTS posts_fts;
DROP TRIGGER IF EXISTS posts_fts_insert;
DROP TRIGGER IF EXISTS posts_fts_update;
DROP TRIGGER IF EXISTS posts_fts_delete;

-- ============================================================================
-- 1. Create FTS5 Virtual Table with content column
-- ============================================================================
-- Content = message_text + metadata keywords (extracted from JSON)
CREATE VIRTUAL TABLE posts_fts USING fts5(
    content,
    tokenize='unicode61'
);

-- ============================================================================
-- 2. Populate FTS5 with existing data
-- ============================================================================
-- Extract keywords from JSON metadata on-the-fly using json_extract()
INSERT INTO posts_fts(rowid, content)
SELECT
    post_id,
    message_text || ' ' || COALESCE(json_extract(post_metadata, '$.keywords'), '')
FROM posts
WHERE LENGTH(COALESCE(message_text, '')) > 30;

-- ============================================================================
-- 3. Create Triggers for Automatic Sync
-- ============================================================================
-- INSERT trigger: extract keywords from JSON on-the-fly
CREATE TRIGGER posts_fts_insert AFTER INSERT ON posts
WHEN LENGTH(COALESCE(new.message_text, '')) > 30
BEGIN
    INSERT INTO posts_fts(rowid, content)
    VALUES (
        new.post_id,
        new.message_text || ' ' || COALESCE(json_extract(new.post_metadata, '$.keywords'), '')
    );
END;

-- UPDATE trigger: fires on message_text OR post_metadata change
CREATE TRIGGER posts_fts_update AFTER UPDATE OF message_text, post_metadata ON posts
BEGIN
    -- Always delete old entry
    DELETE FROM posts_fts WHERE rowid = old.post_id;
    -- Insert new entry with combined content if >30 chars
    INSERT INTO posts_fts(rowid, content)
    SELECT
        new.post_id,
        new.message_text || ' ' || COALESCE(json_extract(new.post_metadata, '$.keywords'), '')
    WHERE LENGTH(COALESCE(new.message_text, '')) > 30;
END;

-- DELETE trigger
CREATE TRIGGER posts_fts_delete AFTER DELETE ON posts
BEGIN
    DELETE FROM posts_fts WHERE rowid = old.post_id;
END;

-- ============================================================================
-- 4. Verification
-- ============================================================================
-- Run these queries to verify the migration:
-- SELECT COUNT(*) FROM posts_fts;  -- Should match posts with >30 chars
-- SELECT content FROM posts_fts WHERE rowid = 1;  -- Should show text + keywords
-- SELECT * FROM posts_fts WHERE posts_fts MATCH 'rag vector' LIMIT 5;  -- Test metadata search
