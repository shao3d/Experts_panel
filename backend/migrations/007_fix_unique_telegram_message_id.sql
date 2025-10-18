-- Fix UNIQUE constraint: telegram_message_id should be unique per channel, not globally
-- Migration 007: Fix telegram_message_id UNIQUE constraint

-- Step 1: Create new table with correct constraint
CREATE TABLE posts_new (
	post_id INTEGER NOT NULL,
	channel_id VARCHAR(255) NOT NULL,
	channel_name VARCHAR(255),
	expert_id VARCHAR(100),
	message_text TEXT,
	author_name VARCHAR(255),
	author_id VARCHAR(255),
	created_at DATETIME,
	edited_at DATETIME,
	view_count INTEGER,
	forward_count INTEGER,
	reply_count INTEGER,
	media_metadata TEXT,
	telegram_message_id INTEGER NOT NULL,
	is_forwarded INTEGER,
	forward_from_channel VARCHAR(255),
	PRIMARY KEY (post_id),
	UNIQUE (telegram_message_id, channel_id)  -- Composite unique constraint
);

-- Step 2: Copy data from old table
INSERT INTO posts_new
SELECT post_id, channel_id, channel_name, expert_id, message_text, author_name, author_id,
       created_at, edited_at, view_count, forward_count, reply_count, media_metadata,
       telegram_message_id, is_forwarded, forward_from_channel
FROM posts;

-- Step 3: Drop old table
DROP TABLE posts;

-- Step 4: Rename new table
ALTER TABLE posts_new RENAME TO posts;

-- Step 5: Recreate indexes
CREATE INDEX ix_posts_expert_id ON posts (expert_id);
CREATE INDEX ix_posts_created_at ON posts (created_at);
CREATE INDEX idx_text_search ON posts (message_text);
CREATE INDEX idx_channel_created ON posts (channel_id, created_at);
