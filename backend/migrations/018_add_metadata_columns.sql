-- ============================================================================
-- Migration: 018_add_metadata_columns.sql
-- Purpose: Add metadata columns for Super-Passport search enhancement
-- Author: Scout Level 2 Upgrade
-- Date: 2026-03-14
-- ============================================================================

-- Add post_metadata column (JSON with primary_topic and keywords)
ALTER TABLE posts ADD COLUMN post_metadata TEXT;

-- Add timestamp for when metadata was generated
ALTER TABLE posts ADD COLUMN metadata_generated_at DATETIME;

-- Create partial index for fast NULL lookup (posts needing enrichment)
CREATE INDEX IF NOT EXISTS idx_posts_post_metadata_null ON posts(post_id) WHERE post_metadata IS NULL;

-- ============================================================================
-- Verification
-- ============================================================================
-- Run these queries to verify the migration:
-- PRAGMA table_info(posts);  -- Should show metadata and metadata_generated_at columns
-- SELECT COUNT(*) FROM posts WHERE metadata IS NULL;  -- Posts needing enrichment
