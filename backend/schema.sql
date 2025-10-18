-- SQLite Database Schema for Experts Panel
-- Generated from SQLAlchemy models
-- Enable foreign keys: PRAGMA foreign_keys = ON;

-- Posts table: Stores Telegram channel posts
CREATE TABLE IF NOT EXISTS posts (
    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id VARCHAR(100) NOT NULL,
    channel_name VARCHAR(255),
    message_text TEXT,
    author_name VARCHAR(255),
    author_id VARCHAR(100),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    edited_at DATETIME,
    view_count INTEGER DEFAULT 0,
    forward_count INTEGER DEFAULT 0,
    reply_count INTEGER DEFAULT 0,
    media_metadata JSON,
    telegram_message_id INTEGER,
    is_forwarded INTEGER DEFAULT 0,
    forward_from_channel VARCHAR(255)
);

-- Indexes for posts table
CREATE INDEX idx_posts_channel_id ON posts(channel_id);
CREATE INDEX idx_posts_created_at ON posts(created_at);
CREATE INDEX idx_posts_channel_created ON posts(channel_id, created_at);
CREATE INDEX idx_posts_text_search ON posts(message_text);

-- Links table: Stores relationships between posts
CREATE TABLE IF NOT EXISTS links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_post_id INTEGER NOT NULL,
    target_post_id INTEGER NOT NULL,
    link_type VARCHAR(20) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
    FOREIGN KEY (target_post_id) REFERENCES posts(post_id) ON DELETE CASCADE,
    UNIQUE (source_post_id, target_post_id, link_type)
);

-- Indexes for links table
CREATE INDEX idx_links_source_post_id ON links(source_post_id);
CREATE INDEX idx_links_target_post_id ON links(target_post_id);
CREATE INDEX idx_links_source_type ON links(source_post_id, link_type);
CREATE INDEX idx_links_target_type ON links(target_post_id, link_type);

-- Comments table: Stores expert annotations
CREATE TABLE IF NOT EXISTS comments (
    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    comment_text TEXT NOT NULL,
    author_name VARCHAR(255) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
);

-- Indexes for comments table
CREATE INDEX idx_comments_post_id ON comments(post_id);
CREATE INDEX idx_comments_post_created ON comments(post_id, created_at);

-- Optional: Full-text search virtual table (FTS5)
-- Uncomment if FTS5 is available and needed
-- CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
--     message_text,
--     content='posts',
--     content_rowid='post_id'
-- );
--
-- -- Trigger to keep FTS index updated
-- CREATE TRIGGER IF NOT EXISTS posts_fts_insert AFTER INSERT ON posts
-- BEGIN
--     INSERT INTO posts_fts(rowid, message_text) VALUES (new.post_id, new.message_text);
-- END;
--
-- CREATE TRIGGER IF NOT EXISTS posts_fts_update AFTER UPDATE OF message_text ON posts
-- BEGIN
--     UPDATE posts_fts SET message_text = new.message_text WHERE rowid = new.post_id;
-- END;
--
-- CREATE TRIGGER IF NOT EXISTS posts_fts_delete AFTER DELETE ON posts
-- BEGIN
--     DELETE FROM posts_fts WHERE rowid = old.post_id;
-- END;