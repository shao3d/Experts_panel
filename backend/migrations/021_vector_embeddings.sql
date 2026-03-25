-- Migration: Add vector embeddings support for hybrid retrieval
-- Created: 2026-03-24

-- Metadata table: tracks which posts have been embedded
CREATE TABLE IF NOT EXISTS post_embeddings (
    post_id INTEGER PRIMARY KEY,
    embedding_model TEXT NOT NULL,
    dimensions INTEGER NOT NULL,
    embedded_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(post_id) ON DELETE CASCADE
);

-- Virtual table for vector search using sqlite-vec
-- expert_id as PARTITION KEY for pre-filtering before KNN
-- created_at as metadata column for date filtering before KNN
CREATE VIRTUAL TABLE IF NOT EXISTS vec_posts USING vec0(
    post_id INTEGER PRIMARY KEY,
    embedding float[768],
    expert_id TEXT PARTITION KEY,
    created_at TEXT  -- metadata column: pre-KNN filter by date
);
