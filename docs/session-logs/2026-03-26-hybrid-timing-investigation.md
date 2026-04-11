# Session Log: Hybrid Retrieval Timing Investigation
**Date:** 2026-03-26
**Participants:** Andrey + AI Coder
**Branch:** `main`
**Commits:** `d54dc50`, `f464f5e`

---

## 📋 Session Summary

This session covered multiple topics:
1. **Reddit search** for opencode CLI MiMo V2 Pro skill documentation
2. **Embs&Keys toggle investigation** — why hybrid search isn't faster
3. **Timing logging implementation** — added per-phase timing to pipeline
4. **Production debugging** — `[PIPELINE]` log not appearing on Fly.io

---

## 🎯 Initial Question

User noticed that the **Embs&Keys toggle** in the UI doesn't seem to affect query speed. The `profile_hybrid_retrieval.py` test script showed "insane" speed improvements, but in practice — no noticeable difference. Asked to investigate.

**Test queries used:**
- "Какими инструментами сейчас удобно делать дашборды в своих системах?"
- "Как правильно настраивать Skills?"
- "Как правильно настроить RAG?"

---

## 🔍 Investigation: What We Found

### 1. Reddit Search (Pre-Investigation)

Before the main investigation, user asked to search Reddit for **opencode CLI skills for MiMo V2 Pro model** to help it maintain project documentation.

**Findings:**
- No specific skill exists for MiMo-V2-Pro documentation
- MiMo-V2-Pro is available on OpenCode (via OpenRouter or Xiaomi API)
- Known issue: MiMo-V2-Pro reasoning tokens get stuck in infinite loops on OpenCode
- General documentation skills exist (`crafting-effective-readmes`, `writing-clearly-and-concisely`) but not model-specific
- User was advised: could create custom `SKILL.md` in `.opencode/skills/` for documentation

### 2. Embs&Keys Toggle — Works Correctly ✅

**Frontend (`frontend/src/components/Sidebar.tsx`):**
- Toggle state: `useSuperPassport` (default: `true`, line 33 of `App.tsx`)
- Visual: orange when ON, gray when OFF
- Sends `use_super_passport: true/false` in API request body (line 107 of `App.tsx`)
- Request body structure:
  ```typescript
  { query, expert_filter: experts, stream_progress: true, include_comments: true, 
    include_comment_groups: true, use_recent_only: useRecentOnly, 
    include_reddit: includeReddit, use_super_passport: useSuperPassport }
  ```

**Backend (`backend/src/api/simplified_query_endpoint.py`):**
- Request model (`backend/src/api/models.py:73`): `use_super_passport: bool = True`
- Line ~983: `if request.use_super_passport and expert_ids:` triggers:
  1. AI Scout → generates FTS5 MATCH query
  2. Embedding → computes query vector ONCE for all experts
  3. Creates circuit breaker
  4. Passes `scout_query` and `query_embedding` to each expert pipeline
- Line ~267: `else` falls through to standard retrieval (load ALL posts via `get_standard_posts_query`)

**`get_standard_posts_query` function** (`simplified_query_endpoint.py:69-80`):
```python
def get_standard_posts_query(db, expert_id, cutoff_date=None, max_posts=None):
    query = db.query(Post).filter(Post.expert_id == expert_id)
    if cutoff_date:
        query = query.filter(Post.created_at >= cutoff_date)
    query = query.order_by(Post.created_at.desc())
    if max_posts:
        query = query.limit(max_posts)
    return query
```
- Loads ALL posts for expert (no filtering by relevance)
- Optional cutoff_date for `use_recent_only`
- Optional max_posts limit

**Confirmed:** Toggle state is correctly propagated from UI → API → pipeline routing.

### 2. Why Hybrid Search Isn't Faster — Root Cause Analysis

**Standard Mode (OFF):**
```
Load ALL posts from DB (~20-50ms)
    ↓
Map Phase (Gemini) scores all posts
    ↓
Continue pipeline
```

**Hybrid Mode (ON):**
```
AI Scout (Gemini call)           → +200-800ms
Embedding API call               → +200-500ms (computed once, shared across experts)
Vector KNN search (sqlite-vec)   → +5ms
FTS5 BM25 search                 → +10ms
Soft Freshness scoring           → +5ms
RRF merge                        → +1ms
Post loading from DB             → +20ms
    ↓
Map Phase (Gemini) scores filtered posts
    ↓
Continue pipeline
```

**Key insight:** Hybrid mode adds **~400-1350ms overhead** on the retrieval stage alone. The speed benefit only comes from Map Phase processing fewer posts. But:
- Map Phase uses `MAP_MAX_PARALLEL = 25` (parallel chunk processing)
- Difference between "40 chunks" and "3 chunks" = maybe 1 round (40/25=2 vs 3/25=1)
- For experts with <500 posts, hybrid is **slower** than standard
- `profile_hybrid_retrieval.py` tests retrieval in isolation, not the full pipeline

### 3. Fallback Behavior

`HybridRetrievalService.search_posts()` (`backend/src/services/hybrid_retrieval_service.py:78-92`):
- If no embeddings exist for expert → fallback to standard (load ALL posts)
- If vector/FTS5 returns empty → fallback to standard
- If expert has few posts, RRF might return same set as loading everything

---

## 🛠️ What We Implemented

### Commit `d54dc50`: Detailed Timing Logging

**File: `backend/src/services/hybrid_retrieval_service.py`**
- Added `import time`
- Wrapped each retrieval step in `time.perf_counter()` timers
- Added `stats["timings_ms"]` dict with per-stage breakdown
- Added structured log line:
  ```
  [Hybrid Retrieval] doronin: vector=5.2ms (150) | fts5=12.1ms (87) | rrf=1.3ms (210) | load=18.5ms (210) | total=37.1ms
  ```

**File: `backend/src/api/simplified_query_endpoint.py`**
- Added `timings = {}` dict at start of `process_expert_pipeline()`
- Added timing around each phase:
  - `t_map` — Map Phase timing
  - `t_medium` — Medium Scoring timing
  - `t_resolve` — Resolve timing
  - `t_reduce` — Reduce timing
  - `t_validate` — Language Validation timing
  - `t_comments` — Comment Groups timing
- Added retrieval stats to `timings["retrieval"]`
- Added summary log at the end:
  ```
  [PIPELINE] doronin | mode=hybrid | posts_in=450 -> posts_out=12 | map=3200ms | medium_scoring=1500ms | resolve=800ms | reduce=2500ms | validation=600ms | comment_groups=1200ms | total=18500ms
  ```

### Commit `f464f5e`: Unicode Fix
- Replaced Unicode arrow `→` with ASCII `->` in `[PIPELINE]` log message
- Hypothesis: Unicode character might cause encoding issues in Fly.io logging

---

## ⚠️ Current Blocker: `[PIPELINE]` Log Not Appearing

### What Works
- ✅ Code is deployed and verified on Fly.io machine (`flyctl ssh console`)
- ✅ Line 644-648 contains the `[PIPELINE]` log
- ✅ Other `logger.info()` calls work (e.g., `[DEBUG CGS]`, `[DEBUG] comment_group_results count`)
- ✅ Query processing completes successfully (200 OK)
- ✅ Comment groups processing visible in logs (e.g., `[DEBUG CGS] process() called for expert_id=doronin`)
- ✅ Full pipeline executes (Map → Medium Scoring → Resolve → Reduce → Validation → Comment Groups)
- ✅ `logger = logging.getLogger(__name__)` at line 63 — same logger as other working logs

### What Doesn't Work
- ❌ `[PIPELINE]` log never appears in `flyctl logs`
- ❌ `[Hybrid Retrieval]` log from `hybrid_retrieval_service.py` also not appearing
- ❌ Tried Unicode fix (`→` → `->`) — didn't help
- ❌ Machine restart via `flyctl machine restart` — didn't help

### Verified Deployments
| Timestamp (UTC) | Action | Image | Version | Notes |
|-----------------|--------|-------|---------|-------|
| 23:01:08Z | GitHub Actions auto-deploy | `deployment-01KMP62WSQWW1AT0FTN2THYB3N` | 274 | Docs commit `93ddbe9` (on top of `d54dc50`) |
| 23:24:14Z | Manual `flyctl deploy --remote-only --strategy immediate` | `deployment-01KMP7BK3CE6DY4ZV2H9V914J3` | 275 | Direct deploy with timing code |
| 23:32:17Z | GitHub Actions auto-deploy (Unicode fix) | `deployment-01KMP7TJA4ACDK7VNKW9K4FWXC` | 276 | Unicode arrow replaced, final deploy |

### Full Debugging Timeline

| Time (UTC) | Action | Result |
|------------|--------|--------|
| 22:59:57Z | Push commit `d54dc50` to GitHub | Auto-deploy triggered |
| 23:01:08Z | Deploy completes (run `23622202066`) | Success |
| 23:05:46Z | User runs query "Как правильно настраивать Skills?" | POST 200 OK |
| 23:07:37Z | Machine autostops (idle) | — |
| 23:11:24Z | Machine restarts (user opens app) | — |
| 23:12:23Z | User runs query "Как правильно настроить RAG?" | POST 200 OK, no `[PIPELINE]` |
| 23:12:40-23:13:02Z | Comment groups processing visible | `[DEBUG CGS]` logs appear |
| ~23:15Z | Check `flyctl logs` with grep | No `[PIPELINE]` found |
| ~23:16Z | `flyctl machine restart 7817664f944918` | Restarted, no change |
| ~23:18Z | SSH into machine, verify code at line 644-648 | Code confirmed present |
| ~23:19Z | Check logger config at line 63 | `logger = logging.getLogger(__name__)` confirmed |
| ~23:20Z | Check full logs without grep | No `[PIPELINE]` entries |
| ~23:22Z | Replace `→` with `->` in log message | Commit `f464f5e` |
| 23:24:14Z | Manual `flyctl deploy` | New image deployed |
| 23:26:01Z | User runs query again | POST 200 OK, still no `[PIPELINE]` |
| 23:34:49Z | User runs another query | POST 200 OK, still no `[PIPELINE]` |
| ~23:36Z | SSH verify code with `->` | Confirmed, still not logging |

### Debugging Commands Used
```bash
# Check deployed image
flyctl image show -a experts-panel

# Check machine status
flyctl status -a experts-panel
flyctl machine ls -a experts-panel

# Check logs
flyctl logs -a experts-panel -n 2>&1 | grep -E "PIPELINE|Hybrid Retrieval"
flyctl logs -a experts-panel -n 2>&1 | grep "POST /api/v1/query"
flyctl logs -a experts-panel -n 2>&1 | grep "23:34" | grep -v "log-batch\|GET /"

# SSH into machine to verify code
flyctl ssh console -a experts-panel -C "sed -n '644,648p' /app/src/api/simplified_query_endpoint.py"
flyctl ssh console -a experts-panel -C "grep -n 'PIPELINE' /app/src/api/simplified_query_endpoint.py"

# Force deploy
flyctl deploy -a experts-panel --remote-only --strategy immediate

# Force restart
flyctl machine restart 7817664f944918 -a experts-panel
```

### Hypotheses (Unverified)

**H1: Exception before log line**
- `process_expert_pipeline()` might throw an exception between comment groups processing (line ~625) and the log (line 644)
- Evidence: Comment groups processing completes (visible in logs), but log never fires
- Need to check: add `try/except` around the log and print traceback

**H2: Log buffering in Fly.io**
- `logger.info()` might be buffered and not flushed to stdout
- Fly.io reads stdout/stderr for logs — if buffer not flushed, log never appears
- Evidence: Other `logger.info()` calls work, but they might be flushed by different mechanism
- Need to try: `import sys; sys.stdout.flush()` after the log

**H3: Different execution path**
- Maybe the query runs through a different code path (e.g., Reddit-only mode, or video_hub)
- Evidence: `[DEBUG CGS]` logs show multiple experts being processed (neuraldeep, ai_architect, silicbag, kornish, doronin) — so normal pipeline IS running
- Need to check: add log at function entry point to confirm function is called

**H4: Logging level configuration**
- Maybe the deployed uvicorn is filtering out certain log messages
- Evidence: `uvicorn --log-level info` — INFO should be visible
- But maybe custom loggers need explicit handler configuration
- Need to check: `backend/src/api/main.py` for logging setup

**H5: Exception in `timings` dict access**
- Maybe `retrieval_stats.get("mode", "standard")` throws an exception if `retrieval_stats` is not a dict
- Evidence: `timings["retrieval"]` is set from `HybridRetrievalService.search_posts()` return value
- Need to check: add defensive checks around dict access

**H6: Silent exception in process_expert_pipeline**
- The function might be wrapped in a try/except in `event_generator_parallel()` (line ~1300-1350) that catches exceptions and doesn't re-raise
- Evidence: User sees results in UI, so pipeline completes, but maybe with error
- Need to check: look at error handling in `event_generator_parallel()`

### Recommended Next Steps for Next Coder

1. **Add flush to logging:**
   ```python
   import sys
   logger.info(...)
   sys.stdout.flush()
   ```

2. **Add try/except around the log:**
   ```python
   try:
       logger.info(...)
   except Exception as e:
       print(f"LOG ERROR: {e}")
   ```

3. **Add entry log at function start:**
   ```python
   async def process_expert_pipeline(...):
       logger.info(f"[DEBUG] process_expert_pipeline called for {expert_id}")
       ...
   ```

4. **Check if there's a different code path:**
   - Look at `event_generator_parallel()` around line 1300-1350
   - Check if `process_expert_pipeline()` is called directly or wrapped in try/except that catches errors silently

5. **Try `print()` instead of `logger.info()`:**
   ```python
   print(f"[PIPELINE] {expert_id} | mode={mode} | ...", flush=True)
   ```

6. **Check uvicorn logging config:**
   - Look at `backend/src/api/main.py` for logging setup
   - Maybe custom loggers need explicit handler configuration

---

## 📁 Files Modified

| File | Commit | Changes |
|------|--------|---------|
| `backend/src/services/hybrid_retrieval_service.py` | `d54dc50` | Added `import time`, timing around each retrieval step, `stats["timings_ms"]` |
| `backend/src/api/simplified_query_endpoint.py` | `d54dc50` | Added `timings = {}`, timing around each pipeline phase, summary `[PIPELINE]` log |
| `backend/src/api/simplified_query_endpoint.py` | `f464f5e` | Replaced Unicode `→` with ASCII `->` in log message |

**Files read but not modified:**
- `frontend/src/components/Sidebar.tsx` — confirmed toggle logic
- `frontend/src/App.tsx` — confirmed state management and API request
- `backend/src/config.py` — confirmed config values
- `backend/src/api/models.py` — confirmed `QueryRequest` model
- `backend/src/services/fts5_retrieval_service.py` — confirmed FTS5 search
- `backend/src/services/map_service.py` — confirmed Map phase
- `backend/scripts/profile_hybrid_retrieval.py` — analyzed test script

---

## 📊 Architecture Context

### Pipeline Flow (when `use_super_passport=True`)
```
Orchestrator (simplified_query_endpoint.py)
    ↓
AI Scout (ai_scout_service.py) — generates FTS5 MATCH query (Gemini)
    ↓
Embedding Service (embedding_service.py) — computes query vector ONCE for all experts
    ↓
[For each expert in parallel]:
    HybridRetrievalService.search_posts()
        → Vector KNN (sqlite-vec, dim=768, gemini-embedding-001)
        → FTS5 BM25 (sanitized by sanitize_fts5_query)
        → Soft Freshness scoring (max penalty 0.7 over 1 year)
        → RRF merge (k=60, weights: vector=0.6, fts5=0.4)
        → Load posts from DB (preserving RRF order)
    ↓
    MapService (map_service.py) — Gemini scores posts HIGH/MEDIUM/LOW
        → Chunks of 100, parallel MAP_MAX_PARALLEL (25)
        → 3-layer retry system
    ↓
    MediumScoringService (if medium_posts) — Gemini reranks MEDIUM
        → Score threshold ≥ 0.7, max 5 posts
    ↓
    SimpleResolveService — loads linked posts for HIGH (Depth 1)
    ↓
    ReduceService — Gemini synthesizes answer (max 50 posts context)
    ↓
    LanguageValidationService — ensures language matches query (RU/EN)
    ↓
    CommentGroupMapService — finds relevant comment groups
        → Prioritizes author clarifications on main sources
    ↓
    CommentSynthesisService — synthesizes community insights
    ↓
    ExpertResponse
```

### Pipeline Flow (when `use_super_passport=False`)
```
Orchestrator (simplified_query_endpoint.py)
    ↓
[No AI Scout, No Embedding]
    ↓
[For each expert in parallel]:
    get_standard_posts_query() — loads ALL posts from DB
    ↓
    MapService (map_service.py) — Gemini scores ALL posts
    ↓
    ... (same as above)
```

### Key Config Values
- `MODEL_MAP`: `gemini-2.5-flash-lite` — ultra-fast relevance detection
- `MODEL_SYNTHESIS`: `gemini-3-flash-preview` — pro-grade reasoning
- `MODEL_ANALYSIS`: `gemini-2.0-flash` — translation/validation
- `MODEL_MEDIUM_SCORING`: `gemini-2.0-flash` — content scoring
- `MODEL_COMMENT_GROUPS`: `gemini-2.0-flash` — comment relevance
- `MODEL_SCOUT`: `gemini-3.1-flash-lite-preview` — AI Scout / FTS5
- `MAP_MAX_PARALLEL`: 25 (Tier 1) / 8 (Free)
- `MEDIUM_MAX_SELECTED_POSTS`: 5
- `MEDIUM_SCORE_THRESHOLD`: 0.7
- `HYBRID_VECTOR_TOP_K`: 150
- `HYBRID_FTS5_TOP_K`: 100
- `HYBRID_RRF_K`: 60

### Key Code Locations
- `process_expert_pipeline()`: `simplified_query_endpoint.py:190-663`
- `HybridRetrievalService.search_posts()`: `hybrid_retrieval_service.py:51-166`
- `get_standard_posts_query()`: `simplified_query_endpoint.py:69-80`
- `event_generator_parallel()`: `simplified_query_endpoint.py:960-1470`
- `AI Scout`: `simplified_query_endpoint.py:983-1017`
- `Embedding pre-compute`: `simplified_query_endpoint.py:1057-1066`
- `Circuit breaker`: `simplified_query_endpoint.py:118-155`

---

## 🔧 Fly.io CLI Reference

### Common Commands Used
```bash
# Auth & Apps
flyctl auth whoami                          # Check auth (literavision@gmail.com)
flyctl apps list                            # List apps (experts-panel deployed)

# Deployment
flyctl deploy -a experts-panel --remote-only --strategy immediate  # Deploy
flyctl status -a experts-panel              # Check app status
flyctl machine ls -a experts-panel          # List machines
flyctl image show -a experts-panel          # Check deployed image SHA

# Logs
flyctl logs -a experts-panel -n             # Get recent logs (no tail)
flyctl logs -a experts-panel -n 2>&1 | grep "PIPELINE"  # Filter logs

# SSH (check deployed code)
flyctl ssh console -a experts-panel -C "cat /app/src/api/simplified_query_endpoint.py"  # Read file
flyctl ssh console -a experts-panel -C "sed -n '644,648p' /app/src/api/simplified_query_endpoint.py"  # Read lines

# Machine Management
flyctl machine restart 7817664f944918 -a experts-panel  # Force restart
```

### GitHub CLI Reference
```bash
# Check deploy workflow
gh run list --limit 5                       # List recent runs
gh run view 23622202066 --log               # View deploy log
```

---

## 🚀 Production Info
- **Platform:** Fly.io
- **App:** `experts-panel`
- **Hostname:** `experts-panel.fly.dev`
- **Region:** iad (US East)
- **Machine ID:** `7817664f944918`
- **Machine Name:** `wild-snow-2372`
- **Size:** `shared-cpu-1x:1024MB`
- **Volume:** `vol_vgj6w3gp517d2lpv`
- **Deploy:** via GitHub Actions (auto-deploy on push to `main`)
- **CLI:** `flyctl` v0.4.26
- **Auth:** `literavision@gmail.com`
- **GitHub Repo:** `shao3d/Experts_panel`
- **Auto-deploy workflow:** "Deploy to Fly.io" (triggers on push to main)
