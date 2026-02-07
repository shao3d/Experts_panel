# Project Context: Experts Panel

**Last Updated:** 2026-02-07
**Status:** Production (Stable) - Tier 1 Optimized

## 🎯 Quick Start for AI Agent

**To get full context, read these files in order:**
1. This file (auto-loaded via User Rules)
2. `docs/pipeline-architecture.md` — **Primary Source of Truth** for logic & models.
3. `backend/CLAUDE.md` — Backend details (services mapping).
4. `frontend/CLAUDE.md` — Frontend components.

## 🏗️ Core Architecture
- **What:** Multi-expert RAG system processing Telegram channels via 8-phase pipeline
- **Stack:** FastAPI + React + SQLite + Fly.io
- **LLM Strategy:**
    - **Map:** `gemini-2.5-flash-lite`
    - **Synthesis/Reduce:** `gemini-3-flash-preview`
    - **Analysis:** `gemini-2.0-flash`
- **Reddit:** Parallel pipeline via Sidecar Proxy (`experts-reddit-proxy`) to bypass IP blocks.
- **Key Management:** Single API key with auto-retry on rate limits (65s wait)

## 🔧 Critical Configuration
| Setting | Value | Location |
|---------|-------|---------|
| Map Model | gemini-2.5-flash-lite | `MODEL_MAP` env |
| Synthesis Model | gemini-3-flash-preview | `MODEL_SYNTHESIS` env |
| Drift Model | gemini-3-flash-preview | `MODEL_DRIFT_ANALYSIS` env |
| Date Filter | use_recent_only (3 months) | `QueryRequest` parameter |

## 🚀 Deployment
- **Platform:** Fly.io (auto-deploy via GitHub Actions)
- **Manage secrets:** `fly secrets set/unset/list`

## 📁 Key Files Reference
```
backend/
├── src/config.py          # All env/model config (Check here for model versions)
├── src/api/simplified_query_endpoint.py  # Main pipeline orchestration
├── src/services/
│   ├── map_service.py              # Phase 1: Map
│   ├── medium_scoring_service.py   # Phase 2: Scoring
│   ├── simple_resolve_service.py   # Phase 3: Resolve
│   ├── reduce_service.py           # Phase 4: Reduce
│   ├── reddit_enhanced_service.py  # Phase 8: Reddit Proxy Client
│   └── google_ai_studio_client.py  # Unified LLM Client
```