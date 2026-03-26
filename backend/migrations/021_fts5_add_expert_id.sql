-- ============================================================================
-- Migration: 021_fts5_add_expert_id.sql
-- Purpose: Add expert_id UNINDEXED + created_at UNINDEXED to FTS5 table
--          Eliminates JOIN with posts table for expert_id filtering
--          Reduces query time from ~6000ms to ~30ms
-- Date: 2026-03-26
-- ============================================================================

-- Drop existing FTS5 table and triggers
DROP TABLE IF EXISTS posts_fts;
DROP TRIGGER IF EXISTS posts_fts_insert;
DROP TRIGGER IF EXISTS posts_fts_update;
DROP TRIGGER IF EXISTS posts_fts_delete;

-- ============================================================================
-- 1. Create FTS5 Virtual Table with expert_id and created_at as UNINDEXED
-- ============================================================================
-- UNINDEXED columns: stored in FTS5, available for SELECT/WHERE, but NOT
-- included in the full-text index. This allows filtering without JOIN.
CREATE VIRTUAL TABLE posts_fts USING fts5(
    content,
    expert_id UNINDEXED,
    created_at UNINDEXED,
    tokenize='unicode61'
);

-- ============================================================================
-- 2. Populate FTS5 with existing data
-- ============================================================================
INSERT INTO posts_fts(rowid, content, expert_id, created_at)
SELECT
    post_id,
    message_text || ' ' || COALESCE(json_extract(post_metadata, '$.keywords'), ''),
    expert_id,
    created_at
FROM posts
WHERE LENGTH(COALESCE(message_text, '')) > 30;

-- ============================================================================
-- 3. Create Triggers for Automatic Sync
-- ============================================================================
CREATE TRIGGER posts_fts_insert AFTER INSERT ON posts
WHEN LENGTH(COALESCE(new.message_text, '')) > 30
BEGIN
    INSERT INTO posts_fts(rowid, content, expert_id, created_at)
    VALUES (
        new.post_id,
        new.message_text || ' ' || COALESCE(json_extract(new.post_metadata, '$.keywords'), ''),
        new.expert_id,
        new.created_at
    );
END;

CREATE TRIGGER posts_fts_update AFTER UPDATE OF message_text, post_metadata ON posts
WHEN LENGTH(COALESCE(new.message_text, '')) > 30
BEGIN
    DELETE FROM posts_fts WHERE rowid = old.post_id;
    INSERT INTO posts_fts(rowid, content, expert_id, created_at)
    VALUES (
        new.post_id,
        new.message_text || ' ' || COALESCE(json_extract(new.post_metadata, '$.keywords'), ''),
        new.expert_id,
        new.created_at
    );
END;

CREATE TRIGGER posts_fts_delete AFTER DELETE ON posts
BEGIN
    DELETE FROM posts_fts WHERE rowid = old.post_id;
END;
