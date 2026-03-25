# Scout Next Steps: Metadata Enrichment

**Created:** 2026-03-14
**Updated:** 2026-03-14
**Status:** Phase 1-3 Complete, Phase 4 Pending
**Goal:** Improve Recall to 80%+ via Pre-computed Metadata

---

## 📊 Implementation Progress

### Phase 1: UI Toggle ✅ COMPLETE

| File | Status | Notes |
|------|--------|-------|
| `frontend/src/types/api.ts` | ✅ Done | Added `use_super_passport?: boolean` |
| `frontend/src/App.tsx` | ✅ Done | State + API call + mobile checkbox |
| `frontend/src/components/Sidebar.tsx` | ✅ Done | Toggle UI with yellow accent |

**Implementation Notes:**
- Toggle added to Sidebar (desktop) and mobile drawer
- Default: `true` (Super-Passport enabled)
- Passed to API: `use_super_passport: useSuperPassport`

---

### Phase 2: Metadata Enrichment Cron ✅ COMPLETE

| File | Status | Notes |
|------|--------|-------|
| `backend/src/models/post.py` | ✅ Done | Added `post_metadata`, `metadata_generated_at` |
| `backend/src/config.py` | ✅ Done | Added `METADATA_MODEL`, `METADATA_BATCH_SIZE` |
| `backend/scripts/enrich_post_metadata.py` | ✅ Done | Async cron script with dry-run |
| `backend/prompts/metadata_prompt.txt` | ✅ Done | JSON output prompt |

**Implementation Notes:**
- Column named `post_metadata` (not `metadata`) due to SQLAlchemy reserved word
- Script uses `SessionLocal` from `base.py` (not `get_db`)
- Proper session management with `try/finally: db.close()`

**Usage:**
```bash
# Dry-run (preview)
python scripts/enrich_post_metadata.py --dry-run --batch-size 10

# Production run
python scripts/enrich_post_metadata.py --batch-size 50
```

---

### Phase 3: FTS5 Rebuild with Metadata ✅ COMPLETE

| File | Status | Notes |
|------|--------|-------|
| `backend/migrations/018_add_metadata_columns.sql` | ✅ Done | Adds `post_metadata`, `metadata_generated_at` |
| `backend/migrations/019_fts5_metadata_rebuild.sql` | ✅ Done | Rebuilds FTS5 with JSON extraction |

**Implementation Notes:**
- Triggers use `json_extract(post_metadata, '$.keywords')` for on-the-fly extraction
- FTS5 content = `message_text || ' ' || keywords`
- UPDATE trigger fires on both `message_text` and `post_metadata` changes

**Verification:**
```sql
-- Check column exists
PRAGMA table_info(posts);  -- Columns 17-18

-- Check FTS5 triggers
SELECT sql FROM sqlite_master WHERE type='trigger' AND tbl_name='posts';

-- Test metadata search
SELECT * FROM posts_fts WHERE posts_fts MATCH 'rag vector' LIMIT 5;
```

---

### Phase 4: A/B Test & Deploy ⏳ PENDING

**Goal:** Verify Metadata Recall ≥ 70%

**Before Testing:**
1. Run enrichment cron to populate metadata for existing posts
2. Verify metadata quality (sample 10 posts)

**Test command:**
```bash
cd backend
python scripts/ab_test_super_passport.py \
  --queries "Как настраивать RAG?" "Kubernetes деплой" "LLM промпты" \
  --experts refat nobilix \
  --timeout 120
```

**Success criteria:**
| Metric | Target |
|--------|--------|
| Recall (RAG query) | ≥ 70% |
| Latency | ≤ OLD pipeline |
| Errors | 0 |

**If success:**
1. Set `HYBRID_SAMPLE_RATIO = 0.0` in `fts5_retrieval_service.py`
2. Deploy to production
3. Monitor for 1 week

**If failure:**
1. Keep `HYBRID_SAMPLE_RATIO = 0.2` as fallback
2. Sample metadata quality (10 random posts)
3. Improve prompt if needed
4. Re-run enrichment

---

## 📁 Files Modified/Created

| Action | File | Status |
|--------|------|--------|
| MODIFY | `frontend/src/types/api.ts` | ✅ |
| MODIFY | `frontend/src/App.tsx` | ✅ |
| MODIFY | `frontend/src/components/Sidebar.tsx` | ✅ |
| MODIFY | `backend/src/models/post.py` | ✅ |
| MODIFY | `backend/src/config.py` | ✅ |
| CREATE | `backend/scripts/enrich_post_metadata.py` | ✅ |
| CREATE | `backend/prompts/metadata_prompt.txt` | ✅ |
| CREATE | `backend/migrations/018_add_metadata_columns.sql` | ✅ |
| CREATE | `backend/migrations/019_fts5_metadata_rebuild.sql` | ✅ |
| CLEANUP | `backend/src/services/fts5_retrieval_service.py` | ⏳ After Phase 4 |

---

## 🧹 Code Cleanup (After Phase 4 Success)

Remove Hybrid Mode from `fts5_retrieval_service.py`:

```python
# DELETE these lines:
HYBRID_SAMPLE_RATIO = 0.2
HYBRID_MIN_SAMPLE = 10

# DELETE this method:
def _get_random_post_ids(self, ...): ...

# DELETE from search_posts():
use_hybrid parameter
random_ids logic
```

---

## ⚠️ Known Issues & Fixes Applied

| Issue | Fix |
|-------|-----|
| SQLAlchemy `metadata` reserved word | Renamed to `post_metadata` |
| `get_db` not exported from `database.py` | Use `SessionLocal` from `base.py` |
| Session leak in cron script | Added `finally: db.close()` |
| FTS5 MATCH syntax with alias | Changed `f.posts_fts MATCH` → `posts_fts MATCH` |
| FTS5 MATCH syntax with alias | Changed `f.posts_fts MATCH` → `posts_fts MATCH` |
| FTS5 MATCH syntax with alias | Changed `f.posts_fts MATCH` → `posts_fts MATCH` |

---

## 🔧 Environment Variables

```bash
# .env.example
METADATA_MODEL=gemini-2.0-flash
METADATA_BATCH_SIZE=50
```

---

## 📝 Architecture Decision Record

**Decision:** Pre-computed Metadata over Random Sample

| Metadata | Random Sample |
|----------|---------------|
| Deterministic results | Random results |
| Pre-computed (no latency) | Runtime cost |
| Semantic understanding | Blind luck |
| One-time $0.10 cost | Per-query cost |

**Rationale:** Metadata is the proper architectural solution. Random Sample was a temporary hack to be removed after validation.
