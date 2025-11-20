-- Migration 010: Backfill posts.channel_username from expert_metadata
-- Created: 2025-01-19
-- Purpose: Populate channel_username for all existing posts

-- Update posts with channel_username from expert_metadata
UPDATE posts
SET channel_username = (
    SELECT em.channel_username
    FROM expert_metadata em
    WHERE em.expert_id = posts.expert_id
)
WHERE expert_id IS NOT NULL;

-- Verification: Check for posts without channel_username
SELECT
    'Backfill verification' as check_name,
    COUNT(*) as posts_with_expert_id,
    COUNT(CASE WHEN channel_username IS NULL THEN 1 END) as missing_channel_username
FROM posts
WHERE expert_id IS NOT NULL;

-- Expected result: missing_channel_username = 0
