# Backend Services - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview)

## 🚀 Backend Service Purpose
FastAPI backend service providing multi-expert query processing with Map-Resolve-Reduce pipeline, real-time SSE streaming, and Reddit integration.

## Narrative Summary
The backend implements a sophisticated 10-phase query processing system. It uses a **Gemini-only** strategy through **OpenRouter**. `vertex_llm_client.py` is retained as an import-compatibility filename, but its canonical runtime client is OpenRouter.

## Key Files & Responsibilities

### Core Pipeline Services
| Service | Phase | Model (Default) | Responsibility |
|---------|-------|-----------------|----------------|
| `ai_scout_service.py` | **0. Scout** | `google/gemini-3.1-flash-lite` | Generates FTS5 MATCH queries (OR-only Entity Clouds). Runs **parallel** with Embedding. |
| `embedding_service.py`| **0. Embed**| `google/gemini-embedding-001` | Pre-computes query embedding once for all experts. Runs **parallel** with Scout. |
| `hybrid_retrieval_service.py` | **0. Retrieval** | *None (SQLite)* | Embs&Keys Hybrid Search (Vector KNN + FTS5 + RRF). Freshness from SQL directly (no extra DB query). |
| `fts5_retrieval_service.py` | **Internal** | *None* | Provides FTS5 query sanitization utils used by Hybrid Service. |
| `map_service.py` | **1. Map** | `gemini-2.5-flash-lite` | Chunks posts (50), scores relevance (HIGH/MEDIUM/LOW). 3-layer retry system. |
| `medium_scoring_service.py` | **2. Score** | `google/gemini-3.1-flash-lite` | Reranks MEDIUM posts. Keeps top 5 with score ≥ 0.7. |
| `simple_resolve_service.py` | **3. Resolve** | *None (DB)* | Expands HIGH posts context (Depth 1). Bypassed for Medium posts. |
| `reduce_service.py` | **4. Reduce** | `gemini-3-flash-preview` | Synthesizes final answer. Max 50 posts context. Validates references. |
| `language_validation_service.py` | **5. Validate** | `google/gemini-3.1-flash-lite` | Ensures response language matches query (RU/EN). |
| `comment_group_map_service.py` | **6. Comments** | `google/gemini-3.1-flash-lite` | Drift scoring runs **parallel** with Reduce. `score_drift_groups()` + `merge_with_main_sources()`. |
| `comment_synthesis_service.py` | **7. Synthesis** | `gemini-3-flash-preview` | Extracts insights into 4 sections (Expert/Community). Runs after Reduce + Drift complete. |
| `video_hub_service.py` | **Video Sidecar** | `gemini-3.1-pro-preview` | **Digital Twin**. 4-phase video analysis (Map -> Resolve -> Synthesis -> Validation). |
| `reddit_enhanced_service.py` | **8. Reddit** | `MODEL_ANALYSIS` (lite) rerank; `MODEL_SYNTHESIS` for comparison-intent + HTTP Proxy | **Sidecar Orchestrator**. Reddit Search V2 runs precision-first candidate generation, early comment enrichment, and answerability-first reranking. |
| `reddit_synthesis_service.py` | **Synthesis** | `gemini-3-flash-preview` | **Staff Engineer Persona**. Finds Hidden Gems & Minority Reports. No Fluff. |
| `meta_synthesis_service.py` | **Meta-Synthesis** | `gemini-3-flash-preview` | Cross-expert unified analysis. Runs parallel with Reddit after all experts complete (≥2). |

### Infrastructure
- `src/api/simplified_query_endpoint.py`: **Main Orchestrator**. Manages parallel expert tasks, SSE streaming with `pipeline_state` tracking, and Reddit Sidecar (120s timeout).
- `src/api/pipeline_state_tracker.py`: **Pipeline State Tracker**. Tracks aggregate phase statuses across all experts (per-expert + cross-cutting). Monotonic priority: pending→active→error/skipped→completed.
- `src/config.py`: **Configuration Hub**. Reads all env vars.
- `src/services/vertex_llm_client.py`: **Canonical OpenRouter LLM Client** (legacy filename). Handles retries, provider capability routing, and rate limits.
- `src/services/google_ai_studio_client.py`: Compatibility shim for legacy imports.
- `src/utils/error_handler.py`: **Error System**. Maps exceptions to user-friendly messages.

## API Endpoints
- `POST /api/v1/query`: Main streaming endpoint.
- `GET /api/v1/experts`: List experts.
- `GET /health`: Cheap cached health diagnostics.
- `GET /health/live`: Forced live diagnostics (admin-protected via `X-Admin-Secret`).

## Reddit Integration
- **Active Client**: `src/services/reddit_enhanced_service.py` (Proxy Client).
- **Architecture**: Hybrid Sidecar.
    - **Search**: via Proxy `POST /search` (direct Reddit OAuth API inside the sidecar).
    - **Details**: via Proxy `POST /details` (deep fetch of 100 comments / depth 5).
- **Search V2 (Precision-First)**:
    - **Soft Subreddit Hints**: Scout still proposes target communities, but backend no longer hard-locks retrieval to them by default.
    - **Tiny Targeted Channel**: For narrow `how_to` / `troubleshooting` / `comparison` intents, backend may add a very small targeted retrieval on the strongest subreddit hints, while keeping global search active.
    - **Smaller Candidate Set**: Backend favors literal query + scout query + freshness/quality channels instead of many additive search hacks.
    - **Early Enrichment**: Top candidates fetch comments before final rerank so answer-bearing comments can influence ranking.
    - **Answerability Rerank**: Gemini scores "does this answer the question?" rather than mere topical similarity.
    - **Stronger Comparison Gate**: `comparison` queries prefer direct title/body matches and explicit comparison markers instead of comment-only overlaps.
    - **Confidence Thresholds**: Low-confidence Reddit results are dropped instead of filling the UI with adjacent noise.
    - **Debug Trace**: Optional structured trace via `REDDIT_SEARCH_DEBUG=true`.
- **Logic**: 
    - **Scout as Hint, not Gate**: topic detection shapes retrieval, but global search always remains available.
    - **Precision > Recall**: Returning fewer high-confidence threads is preferred over broad but noisy recall.
- **Legacy**: `reddit_client.py` removed 2026-08-25 (dead asyncpraw client; manual/legacy scripts that imported it are non-runtime artifacts).

## Configuration (Environment Variables)

### Models
Defined in `.env`, loaded in `config.py`.
- `MODEL_MAP`: `google/gemini-2.5-flash-lite`
- `MODEL_SYNTHESIS`: `google/gemini-3-flash-preview`
- `MODEL_ANALYSIS`: `google/gemini-3.1-flash-lite`
- `MODEL_MEDIUM_SCORING`: `google/gemini-3.1-flash-lite`
- `MODEL_COMMENT_GROUPS`: `google/gemini-3.1-flash-lite`
- `MODEL_DRIFT_ANALYSIS`: `google/gemini-3-flash-preview`
- `MODEL_SCOUT`: `google/gemini-3.1-flash-lite` (AI Scout / FTS5)
- `MODEL_META_SYNTHESIS`: `google/gemini-3-flash-preview` (Cross-expert unified analysis)
- `MODEL_EMBEDDING`: `google/gemini-embedding-001` (Hybrid Retrieval embeddings)
- `MODEL_VIDEO_PRO`: `gemini-3.1-pro-preview` (Video Hub Digital Twin)
- `MODEL_VIDEO_FLASH`: `gemini-3-flash-preview` (Video Hub validation)

### OpenRouter Runtime Notes
- Required auth: `OPENROUTER_API_KEY` (or the compatibility fallback `OPENAI_API_KEY`)
- JSON-producing calls use `provider.require_parameters=true`; providers that cannot honour the requested response format are excluded.
- The Video Hub remains out of the normal runtime health probe and is not part of this migration.
- Backend/API startup and operational CLI scripts explicitly load `backend/.env`; do not rely on the current working directory.

### Env Vars / Tunables
- `MAP_MAX_PARALLEL`: 25 (Tier 1) / 8 (Free)
- `MAP_CHUNK_SIZE`: 50
- `MAX_CONCURRENT_EXPERTS`: 5
- `MEDIUM_MAX_SELECTED_POSTS`: 5
- `MEDIUM_SCORE_THRESHOLD`: 0.7
- `MEDIUM_MAX_POSTS`: 50
- `HYBRID_VECTOR_TOP_K`: 150
- `HYBRID_FTS5_TOP_K`: 100
- `HYBRID_RRF_K`: 60
- `MAX_FTS_RESULTS`: 300
- `USE_SUPER_PASSPORT_DEFAULT`: false
- `FTS5_CIRCUIT_BREAKER_THRESHOLD`: 3
- `META_SYNTHESIS_TIMEOUT_SECONDS`: 120
- `QUERY_RESULTS_DIR`: optional durable UI query result directory
- `QUERY_RESULTS_TTL_DAYS`: 7
- `AGENT_CONTEXT_RESULTS_DIR`: optional backend-saved Panex artifact directory
- `AGENT_CONTEXT_RESULTS_TTL_DAYS`: 7
- `AGENT_CONTEXT_DIGEST_MAX_*`: optional `expert_digest` evidence caps; `0` means all selected evidence for count/char caps
- `AGENT_CONTEXT_DIGEST_MAX_OUTPUT_TOKENS`: 16384
- `PANEX_ARTIFACT_DIR`: optional local Panex CLI artifact directory
- `PANEX_ARTIFACT_TTL_DAYS`: 7
- `REDDIT_SEARCH_DEBUG`: false
- `REDDIT_RERANK_CANDIDATES`: 18
- `REDDIT_PRE_RERANK_ENRICH_LIMIT`: 18 (aligned with RERANK_CANDIDATES; undated Serper discovery candidates are force-enriched on top)
- `REDDIT_MIN_CONFIDENCE`: 0.52
- `REDDIT_SOFT_CONFIDENCE`: 0.44
- `REDDIT_SYNTH_COMMENT_TOP_K`: 12 (top-scored comment roots per source in synthesis context)
- `REDDIT_SYNTH_SOURCE_CHAR_CAP`: 15000 (per-source char cap shared between body and comment tree)

### Hardcoded Runtime Limits
- `Reddit wait after experts`: 120s hard limit in `simplified_query_endpoint.py`
- `Reddit HTTP client timeout`: 60s default in `reddit_enhanced_service.py`

## Development
- **Run**: `./quickstart.sh`
- **Logs**: `backend/data/backend.log`
- **Import Video**: `python3 backend/scripts/import_video_json.py <path_to_json>`
- **Embed Fresh Posts**: `python3 backend/scripts/embed_posts.py --continuous`
- **Run Drift Batch**: `python3 backend/run_drift_service.py` (auto-loads `backend/.env`)
- **Analyze One Drift Group**: `python3 backend/analyze_specific_drift.py <post_id>` (auto-loads `backend/.env`)
- **Eval Reddit Search V2**: `python3 backend/scripts/eval_reddit_search_v2.py`
