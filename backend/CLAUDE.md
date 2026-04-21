# Backend Services - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview)

## 🚀 Backend Service Purpose
FastAPI backend service providing multi-expert query processing with Map-Resolve-Reduce pipeline, real-time SSE streaming, and Reddit integration.

## Narrative Summary
The backend implements a sophisticated 10-phase query processing system. It uses a **Gemini-only** strategy on **Vertex AI** with a unified client (`google_ai_studio_client.py`) that preserves the historical interface while authenticating with a service account and retrying rate limit / timeout failures automatically. `Gemini 3*` models are routed through the Vertex `global` endpoint.

## Key Files & Responsibilities

### Core Pipeline Services
| Service | Phase | Model (Default) | Responsibility |
|---------|-------|-----------------|----------------|
| `ai_scout_service.py` | **0. Scout** | `gemini-3.1-flash-lite-preview` | Generates FTS5 MATCH queries (OR-only Entity Clouds). Runs **parallel** with Embedding. |
| `embedding_service.py`| **0. Embed**| `gemini-embedding-001` | Pre-computes query embedding once for all experts. Runs **parallel** with Scout. |
| `hybrid_retrieval_service.py` | **0. Retrieval** | *None (SQLite)* | Embs&Keys Hybrid Search (Vector KNN + FTS5 + RRF). Freshness from SQL directly (no extra DB query). |
| `fts5_retrieval_service.py` | **Internal** | *None* | Provides FTS5 query sanitization utils used by Hybrid Service. |
| `map_service.py` | **1. Map** | `gemini-2.5-flash-lite` | Chunks posts (50), scores relevance (HIGH/MEDIUM/LOW). 3-layer retry system. |
| `medium_scoring_service.py` | **2. Score** | `gemini-2.5-flash` | Reranks MEDIUM posts. Keeps top 5 with score ≥ 0.7. |
| `simple_resolve_service.py` | **3. Resolve** | *None (DB)* | Expands HIGH posts context (Depth 1). Bypassed for Medium posts. |
| `reduce_service.py` | **4. Reduce** | `gemini-3-flash-preview` | Synthesizes final answer. Max 50 posts context. Validates references. |
| `language_validation_service.py` | **5. Validate** | `gemini-2.5-flash` | Ensures response language matches query (RU/EN). |
| `comment_group_map_service.py` | **6. Comments** | `gemini-2.5-flash` | Drift scoring runs **parallel** with Reduce. `score_drift_groups()` + `merge_with_main_sources()`. |
| `comment_synthesis_service.py` | **7. Synthesis** | `gemini-3-flash-preview` | Extracts insights into 4 sections (Expert/Community). Runs after Reduce + Drift complete. |
| `video_hub_service.py` | **Video Sidecar** | `gemini-3.1-pro-preview` | **Digital Twin**. 4-phase video analysis (Map -> Resolve -> Synthesis -> Validation). |
| `reddit_enhanced_service.py` | **8. Reddit** | `gemini-3-flash-preview` + HTTP Proxy | **Sidecar Orchestrator**. Gemini Scout plans subreddit/query strategy; proxy handles `/search` + `/details`; deep drill fetches 100 comments at depth 5. |
| `reddit_synthesis_service.py` | **Synthesis** | `gemini-3-flash-preview` | **Staff Engineer Persona**. Finds Hidden Gems & Minority Reports. No Fluff. |
| `meta_synthesis_service.py` | **Meta-Synthesis** | `gemini-3-flash-preview` | Cross-expert unified analysis. Runs parallel with Reddit after all experts complete (≥2). |

### Infrastructure
- `src/api/simplified_query_endpoint.py`: **Main Orchestrator**. Manages parallel expert tasks, SSE streaming with `pipeline_state` tracking, and Reddit Sidecar (120s timeout).
- `src/api/pipeline_state_tracker.py`: **Pipeline State Tracker**. Tracks aggregate phase statuses across all experts (per-expert + cross-cutting). Monotonic priority: pending→active→error/skipped→completed.
- `src/config.py`: **Configuration Hub**. Reads all env vars.
- `src/services/google_ai_studio_client.py`: **Unified LLM Client**. Handles Vertex routing, retries, and rate limits.
- `src/services/vertex_ai_auth.py`: **Vertex Auth Layer**. Loads service-account JSON or ADC and refreshes OAuth access tokens.
- `src/utils/error_handler.py`: **Error System**. Maps exceptions to user-friendly messages.

## API Endpoints
- `POST /api/v1/query`: Main streaming endpoint.
- `GET /api/v1/experts`: List experts.
- `GET /health`: Health check.

## Reddit Integration
- **Active Client**: `src/services/reddit_enhanced_service.py` (Proxy Client).
- **Architecture**: Hybrid Sidecar.
    - **Search**: via Proxy `POST /search` (the proxy uses Reddit MCP `search_reddit` under the hood).
    - **Details**: via Proxy `POST /details` (deep fetch of 100 comments / depth 5).
- **New Features (Round 5 - Deep Drill & AI Brain)**:
    - **AI Reranking**: Filters viral noise using Gemini 3 relevance check (80% AI + 20% Engagement).
    - **Smart Deduplication**: Normalized URL/Title check to remove cross-posts.
    - **Temporal Awareness**: Scout detects "Fast-moving" vs "Evergreen" intent (`time="month"` vs `"all"`).
    - **Deep Trees**: Fetches 100 comments/post (Depth 5).
    - **Staff Engineer Persona**: Synthesis focused on "Hidden Gems".
    - **Timeless Classics**: Strategy for guides.
- **Logic**: 
    - **Strict Mode**: If topic found -> Search **ONLY** target subreddits.
    - **Auto-detection**: Service automatically detects topic.
- **Legacy**: `reddit_client.py` (Direct `asyncpraw`) - deprecated/fallback only.

## Configuration (Environment Variables)

### Models
Defined in `.env`, loaded in `config.py`.
- `MODEL_MAP`: `gemini-2.5-flash-lite`
- `MODEL_SYNTHESIS`: `gemini-3-flash-preview`
- `MODEL_ANALYSIS`: `gemini-2.5-flash`
- `MODEL_MEDIUM_SCORING`: `gemini-2.5-flash`
- `MODEL_COMMENT_GROUPS`: `gemini-2.5-flash`
- `MODEL_DRIFT_ANALYSIS`: `gemini-3-flash-preview`
- `MODEL_SCOUT`: `gemini-3.1-flash-lite-preview` (AI Scout / FTS5)
- `MODEL_META_SYNTHESIS`: `gemini-3-flash-preview` (Cross-expert unified analysis)
- `MODEL_EMBEDDING`: `gemini-embedding-001` (Hybrid Retrieval embeddings)
- `MODEL_VIDEO_PRO`: `gemini-3.1-pro-preview` (Video Hub Digital Twin)
- `MODEL_VIDEO_FLASH`: `gemini-3-flash-preview` (Video Hub validation)

### Vertex Runtime Notes
- Preferred auth: `VERTEX_AI_SERVICE_ACCOUNT_JSON` or `VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH`
- `VERTEX_AI_PROJECT_ID` and `VERTEX_AI_LOCATION` are required for deterministic production config
- `Gemini 3*` models must use Vertex `global` endpoint; the unified client handles this automatically
- This GCP project does not expose `gemini-2.0-flash`, so the closest production replacement is `gemini-2.5-flash`

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

### Hardcoded Runtime Limits
- `Reddit wait after experts`: 120s hard limit in `simplified_query_endpoint.py`
- `Reddit HTTP client timeout`: 60s default in `reddit_enhanced_service.py`

## Development
- **Run**: `./quickstart.sh`
- **Logs**: `backend/data/backend.log`
- **Import Video**: `python3 backend/scripts/import_video_json.py <path_to_json>`
