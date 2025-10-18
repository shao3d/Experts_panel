-- Migration: Add sync_state table for incremental Telegram sync
-- Created: 2025-10-09
-- Purpose: Track last synced message ID per channel for incremental updates

CREATE TABLE IF NOT EXISTS sync_state (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_username TEXT UNIQUE NOT NULL,
    last_synced_message_id INTEGER,
    last_synced_at TIMESTAMP,
    total_posts_synced INTEGER DEFAULT 0,
    total_comments_synced INTEGER DEFAULT 0
);

-- Initialize with current max telegram_message_id from posts table
INSERT OR IGNORE INTO sync_state (channel_username, last_synced_message_id, last_synced_at)
VALUES ('nobilix', (SELECT MAX(telegram_message_id) FROM posts), datetime('now'));

-- Create index for fast channel lookup
CREATE INDEX IF NOT EXISTS idx_sync_state_channel ON sync_state(channel_username);
