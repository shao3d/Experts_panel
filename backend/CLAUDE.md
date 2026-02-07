# Backend Services - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview)

## 🚀 Backend Service Purpose
FastAPI backend service providing multi-expert query processing with Map-Resolve-Reduce pipeline, real-time SSE streaming, and Reddit integration.

## Narrative Summary
The backend implements a sophisticated 8-phase query processing system. It uses a **Gemini-only** strategy with a unified client (`google_ai_studio_client.py`) that handles key rotation and rate limits (429 errors).

## Key Files & Responsibilities

### Core Pipeline Services
| Service | Phase | Model (Default) | Responsibility |
|---------|-------|-----------------|----------------|
| `map_service.py` | **1. Map** | `gemini-2.5-flash-lite` | Chunks posts (100), scores relevance (HIGH/MEDIUM/LOW). 3-layer retry system. |
| `medium_scoring_service.py` | **2. Score** | `gemini-2.0-flash` | Reranks MEDIUM posts. Keeps top 5 with score ≥ 0.7. |
| `simple_resolve_service.py` | **3. Resolve** | *None (DB)* | Expands HIGH posts context (Depth 1). Bypassed for Medium posts. |
| `reduce_service.py` | **4. Reduce** | `gemini-3-flash-preview` | Synthesizes final answer. Max 50 posts context. Validates references. |
| `language_validation_service.py` | **5. Validate** | `gemini-2.0-flash` | Ensures response language matches query (RU/EN). |
| `comment_group_map_service.py` | **6. Comments** | `gemini-2.0-flash` | Finds comment groups. Prioritizes author clarifications on main sources. |
| `comment_synthesis_service.py` | **7. Synthesis** | `gemini-3-flash-preview` | Extracts insights into 4 sections (Expert/Community). |
| `reddit_enhanced_service.py` | **8. Reddit** | *None (HTTP Proxy)* | **Sidecar Proxy Client**. Deep Comment Trees (Depth 3, Limit 50). Smart Targeting. |
| `reddit_synthesis_service.py` | **Synthesis** | `gemini-3-flash-preview` | **Inverted Pyramid Synthesis**. Freshness Check (2026 aware). Critical Filter. |

### Infrastructure
- `src/api/simplified_query_endpoint.py`: **Main Orchestrator**. Manages parallel expert tasks and SSE streaming.
- `src/config.py`: **Configuration Hub**. Reads all env vars.
- `src/services/google_ai_studio_client.py`: **Unified LLM Client**. Handles API keys, retries, and rate limits.
- `src/utils/error_handler.py`: **Error System**. Maps exceptions to user-friendly messages.

## API Endpoints
- `POST /api/v1/query`: Main streaming endpoint.
- `GET /api/v1/experts`: List experts.
- `GET /health`: Health check.

## Reddit Integration
- **Active Client**: `src/services/reddit_enhanced_service.py` (Proxy Client).
- **Architecture**: Uses `experts-reddit-proxy.fly.dev` sidecar service to avoid IP bans.
- **New Features (Round 3)**:
    - **Deep Trees**: Fetches nested comments (Depth 3) and top 50 comments per post.
    - **Inverted Pyramid**: Synthesis format (Solution -> Details -> Debate).
    - **Freshness**: Injects current date to filter outdated info.
    - **Smart Targeting**: Detects AI/Dev/PM topics via keywords.
- **Logic**: 
    - **Strict Mode (Mutual Exclusion)**: If topic found -> Search **ONLY** target subreddits. If no topic -> Global search.
    - **Auto-detection**: Service automatically detects topic if endpoint misses it.
- **Legacy**: `reddit_client.py` (Direct `asyncpraw`) - deprecated/fallback only.

## Configuration (Environment Variables)

### Models
Defined in `.env`, loaded in `config.py`.
- `MODEL_MAP`: `gemini-2.5-flash-lite`
- `MODEL_SYNTHESIS`: `gemini-3-flash-preview`
- `MODEL_ANALYSIS`: `gemini-2.0-flash`
- `MODEL_MEDIUM_SCORING`: `gemini-2.0-flash`
- `MODEL_COMMENT_GROUPS`: `gemini-2.0-flash`
- `MODEL_DRIFT_ANALYSIS`: `gemini-3-flash-preview`

### Limits
- `MAP_MAX_PARALLEL`: 25 (Tier 1) / 8 (Free)
- `MEDIUM_MAX_SELECTED_POSTS`: 5
- `MEDIUM_SCORE_THRESHOLD`: 0.7

## Development
- **Run**: `./quickstart.sh`
- **Logs**: `backend/data/backend.log`
