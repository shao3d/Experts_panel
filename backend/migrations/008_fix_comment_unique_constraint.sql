-- Migration: Fix UNIQUE constraint on telegram_comment_id
-- Problem: telegram_comment_id is globally unique, but different Telegram channels
--          can have comments with the same ID. This blocks importing comments from
--          multiple experts.
-- Solution: Make constraint compound (telegram_comment_id, post_id) so each channel
--           can have its own sequence of comment IDs.

-- Drop the old UNIQUE constraint on telegram_comment_id alone
DROP INDEX IF EXISTS idx_telegram_comment_unique;

-- The compound index idx_telegram_comments already exists, but it's not UNIQUE
-- We need to recreate it as UNIQUE
DROP INDEX IF EXISTS idx_telegram_comments;

-- Create new compound UNIQUE constraint: telegram_comment_id must be unique per post
-- This allows different channels to have comments with same telegram_comment_id
CREATE UNIQUE INDEX idx_telegram_comment_post_unique ON comments (telegram_comment_id, post_id);
