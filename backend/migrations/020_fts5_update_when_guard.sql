-- ============================================================================
-- Migration: 020_fts5_update_when_guard.sql
-- Purpose: Add WHEN guard to UPDATE trigger for consistency and safety
-- Author: Code Review Fix
-- Date: 2026-03-15
-- ============================================================================

-- This migration is defensive programming:
-- The UPDATE trigger already works correctly (INSERT inside has WHERE clause),
-- but adding WHEN guard improves clarity and prevents unnecessary trigger execution.

-- Drop existing UPDATE trigger
DROP TRIGGER IF EXISTS posts_fts_update;

-- Recreate with WHEN guard (consistent with INSERT trigger logic)
-- Only fire when the post has meaningful text (>30 chars)
CREATE TRIGGER posts_fts_update AFTER UPDATE OF message_text, post_metadata ON posts
WHEN LENGTH(COALESCE(new.message_text, '')) > 30
BEGIN
    DELETE FROM posts_fts WHERE rowid = old.post_id;
    INSERT INTO posts_fts(rowid, content)
    VALUES (
        new.post_id,
        new.message_text || ' ' || COALESCE(json_extract(new.post_metadata, '$.keywords'), '')
    );
END;

-- ============================================================================
-- Verification
-- ============================================================================
-- Run these queries to verify the migration:
-- SELECT sql FROM sqlite_master WHERE type='trigger' AND name='posts_fts_update';
-- Expected: CREATE TRIGGER ... WHEN LENGTH(COALESCE(new.message_text, '')) > 30
