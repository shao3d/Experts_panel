-- Migration 005: Add UNIQUE constraint on telegram_message_id
-- Created: 2025-10-11
-- Purpose: Prevent duplicate posts from being inserted

-- SQLite doesn't support ADD CONSTRAINT, so we need to recreate the table

BEGIN TRANSACTION;

-- Create new table with UNIQUE constraint
CREATE TABLE posts_new (
    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_message_id INTEGER NOT NULL UNIQUE,  -- ← UNIQUE constraint
    message_text TEXT NOT NULL,
    author_name TEXT,
    author_username TEXT,
    created_at TIMESTAMP NOT NULL,
    expert_id TEXT NOT NULL,
    channel_username TEXT
);

-- Copy data from old table
INSERT INTO posts_new
SELECT post_id, telegram_message_id, message_text, author_name, author_username, created_at, expert_id, channel_username
FROM posts;

-- Drop old table
DROP TABLE posts;

-- Rename new table
ALTER TABLE posts_new RENAME TO posts;

-- Recreate indexes
CREATE INDEX idx_posts_telegram_message_id ON posts(telegram_message_id);
CREATE INDEX idx_posts_expert_id ON posts(expert_id);

COMMIT;

-- Verification
SELECT 'Migration 005 completed - UNIQUE constraint added' as status;
