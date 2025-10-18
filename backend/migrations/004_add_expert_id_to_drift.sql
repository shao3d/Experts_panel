-- Migration 004: Add expert_id to comment_group_drift table
-- Created: 2025-10-11
-- Purpose: Add expert identification to drift groups for multi-expert support

-- Add expert_id column
ALTER TABLE comment_group_drift ADD COLUMN expert_id VARCHAR(50);

-- Create index for efficient filtering
CREATE INDEX idx_drift_expert_id ON comment_group_drift(expert_id);

-- Verify migration (will show 0 rows since table is empty)
SELECT
    'Migration 004 completed' as status,
    COUNT(*) as total_drift_groups,
    COUNT(CASE WHEN expert_id IS NOT NULL THEN 1 END) as with_expert_id
FROM comment_group_drift;
