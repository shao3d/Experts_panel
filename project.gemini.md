# Project Context: Experts Panel

**Last Updated:** 2026-02-04
**Status:** Production (Stable) - Tier 1 Optimized

## 🎯 Quick Start for AI Agent

**To get full context, read these files in order:**
1. This file (auto-loaded via User Rules)
2. `CLAUDE.md` — Full architecture overview, 8-phase pipeline, key services
3. `backend/CLAUDE.md` — Backend details (config, services, models)
4. `docs/pipeline-architecture.md` — Deep dive into Map-Resolve-Reduce pipeline

## 🏗️ Core Architecture
- **What:** Multi-expert RAG system processing Telegram channels via 8-phase pipeline
- **Stack:** FastAPI + React + SQLite + Fly.io
- **LLM:** Gemini-only (2.5 Flash Lite for map, 3 Flash Preview for synthesis/drift)
- **Key Management:** Single API key with auto-retry on rate limits (65s wait)
- **Streaming:** SSE for real-time progress

## 🔧 Critical Configuration
| Setting | Value | Location |
|---------|-------|---------|
| API Keys | Google Cloud or AI Studio key(s) | Fly.io secrets (GOOGLE_AI_STUDIO_API_KEY) |
| Models | gemini-2.5-flash-lite, gemini-3-flash-preview, gemini-2.0-flash | MODEL_* env vars |
| Map Parallelism | 25 (Tier 1) / 8 (Free Tier) | MAP_MAX_PARALLEL in config.py |
| Chunk Size | 100 posts | config.py |
| Date Filter | use_recent_only (3 months) | QueryRequest parameter |

## 🚀 Deployment
- **Platform:** Fly.io (auto-deploy via GitHub Actions)
- **Manage secrets:** `fly secrets set/unset/list`
- **Check logs:** `fly logs --no-tail`

## 📁 Key Files Reference
```
backend/
├── src/config.py          # All env/model config
├── src/api/simplified_query_endpoint.py  # Main pipeline orchestration
├── src/services/
│   ├── map_service.py              # Phase 1: LLM Listwise Reranking
│   ├── medium_scoring_service.py   # Phase 2: Medium post scoring
│   ├── simple_resolve_service.py   # Phase 3: Link resolution
│   ├── reduce_service.py           # Phase 4: Answer synthesis
│   ├── language_validation_service.py  # Phase 5: Language fix
│   ├── comment_group_map_service.py    # Phase 6: Comment groups
│   └── comment_synthesis_service.py    # Phase 7: Comment synthesis
└── .env                   # Local config (source of truth)
```

## ⚠️ Common Gotchas
1. **Fly.io secrets must match local .env** — After code refactoring, always verify secrets: `fly secrets list` vs `cat backend/.env`
2. **Works locally but not on Fly.io?** — Check MODEL_* env vars on Fly: `fly ssh console -C "env | grep MODEL"`
3. **429 Quota errors** — Auto-waits 65s and retries (automatic recovery)
4. **Date filtering** — `use_recent_only` filters posts, linked posts, and drift groups to last 3 months. Cutoff calculated via `get_cutoff_date()` in `backend/src/utils/date_utils.py`
