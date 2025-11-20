-- Migration 009: Create expert_metadata table
-- Created: 2025-01-19
-- Purpose: Centralize expert metadata (single source of truth)

-- Create expert_metadata table with minimal fields (MVP)
CREATE TABLE expert_metadata (
    expert_id VARCHAR(50) PRIMARY KEY,
    display_name VARCHAR(255) NOT NULL,
    channel_username VARCHAR(255) NOT NULL UNIQUE
);

-- Index for sync script lookups
CREATE INDEX idx_expert_channel ON expert_metadata(channel_username);

-- Populate with existing experts
INSERT INTO expert_metadata (expert_id, display_name, channel_username) VALUES
    ('refat', 'Refat (Tech & AI)', 'nobilix'),
    ('ai_architect', 'AI Architect', 'the_ai_architect'),
    ('neuraldeep', 'Neuraldeep', 'neuraldeep');

-- Verification query
SELECT
    'Migration 009 completed' as status,
    COUNT(*) as experts_added
FROM expert_metadata;
