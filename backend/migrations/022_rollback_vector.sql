-- Rollback: Remove vector embeddings tables
-- Use this to revert if critical issues with sqlite-vec

DROP TABLE IF EXISTS vec_posts;
DROP TABLE IF EXISTS post_embeddings;
