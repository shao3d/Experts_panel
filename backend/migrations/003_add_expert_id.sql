-- Migration 003: Add expert_id field to posts table
-- Created: 2025-10-10
-- Purpose: Support multi-expert architecture by adding expert identification

-- Add expert_id column
ALTER TABLE posts ADD COLUMN expert_id VARCHAR(50);

-- Create index for efficient filtering
CREATE INDEX idx_posts_expert_id ON posts(expert_id);

-- Update existing Refat posts
-- channel_id '2273349814' corresponds to Refat's Telegram channel
UPDATE posts SET expert_id = 'refat' WHERE channel_id = '2273349814';

-- Verify migration results
SELECT
    'Migration 003 completed' as status,
    COUNT(*) as total_posts,
    COUNT(CASE WHEN expert_id IS NOT NULL THEN 1 END) as posts_with_expert_id,
    COUNT(CASE WHEN expert_id = 'refat' THEN 1 END) as refat_posts
FROM posts;
