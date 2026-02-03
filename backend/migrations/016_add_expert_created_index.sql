-- Migration: Add composite index for expert_id + created_at filtering
-- Needed for efficient use_recent_only queries
-- Created: 2026-02-04

CREATE INDEX IF NOT EXISTS idx_posts_expert_created 
ON posts(expert_id, created_at);

-- Verify index creation
SELECT name FROM sqlite_master 
WHERE type='index' AND name='idx_posts_expert_created';
