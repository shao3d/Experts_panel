-- Migration 024: Add drift_embedding column to comment_group_drift
--
-- Purpose: pre-compute embedding of drift_topics at sync time so query-time
--          scoring uses cosine similarity (~1ms) instead of LLM chunked calls (~130s).
--
-- Nullable: existing rows stay null until backfilled by
--           backend/scripts/maintenance/backfill_drift_embeddings.py.
--
-- Storage: numpy.float32 vector serialized via .tobytes(); decoded via .frombuffer.
--          Size: 768 dims * 4 bytes = 3072 bytes per row (≈3KB). Negligible vs drift_topics TEXT.

ALTER TABLE comment_group_drift ADD COLUMN drift_embedding BLOB;
