-- Migration 006: Add UNIQUE constraint on telegram_message_id
-- Created: 2025-10-11
-- Purpose: Prevent duplicate posts (correct version with all columns)

BEGIN TRANSACTION;

-- 1. Create new table with UNIQUE constraint
CREATE TABLE posts_new (
	post_id INTEGER NOT NULL,
	channel_id VARCHAR(100) NOT NULL,
	channel_name VARCHAR(255),
	expert_id VARCHAR(50),
	message_text TEXT,
	author_name VARCHAR(255),
	author_id VARCHAR(100),
	created_at DATETIME NOT NULL,
	edited_at DATETIME,
	view_count INTEGER,
	forward_count INTEGER,
	reply_count INTEGER,
	media_metadata JSON,
	telegram_message_id INTEGER UNIQUE,  -- ← UNIQUE CONSTRAINT HERE
	is_forwarded INTEGER,
	forward_from_channel VARCHAR(255),
	PRIMARY KEY (post_id)
);

-- 2. Copy all data from old table
INSERT INTO posts_new
SELECT post_id, channel_id, channel_name, expert_id, message_text, author_name,
       author_id, created_at, edited_at, view_count, forward_count, reply_count,
       media_metadata, telegram_message_id, is_forwarded, forward_from_channel
FROM posts;

-- 3. Drop old table
DROP TABLE posts;

-- 4. Rename new table
ALTER TABLE posts_new RENAME TO posts;

-- 5. Recreate indexes
CREATE INDEX ix_posts_expert_id ON posts (expert_id);
CREATE INDEX ix_posts_created_at ON posts (created_at);
CREATE INDEX idx_text_search ON posts (message_text);
CREATE INDEX idx_channel_created ON posts (channel_id, created_at);
CREATE INDEX ix_posts_channel_id ON posts (channel_id);
CREATE INDEX ix_posts_telegram_message_id ON posts (telegram_message_id);

COMMIT;

-- Verification
SELECT 'Migration 006 completed - UNIQUE constraint added to telegram_message_id' as status;
