# Project Context: Experts Panel

**Last Updated:** 2025-12-11
**Status:** Production (Gemini-only architecture)

## 🎯 Quick Start for AI Agent

**To get full context, read these files in order:**
1. This file (auto-loaded via User Rules)
2. `CLAUDE.md` — Full architecture overview, 8-phase pipeline, key services
3. `backend/CLAUDE.md` — Backend details (config, services, models)
4. `docs/pipeline-architecture.md` — Deep dive into Map-Resolve-Reduce pipeline

## 🏗️ Core Architecture
- **What:** Multi-expert RAG system processing Telegram channels via 8-phase pipeline
- **Stack:** FastAPI + React + SQLite + Fly.io
- **LLM:** Gemini-only (2.0 Flash/Flash Lite for online, 3 Flash Preview for offline drift) with multi-key rotation (100% free tier)
- **Streaming:** SSE for real-time progress

## 🔧 Critical Configuration
| Setting | Value | Location |
|---------|-------|----------|
| API Keys | 5 Google AI Studio keys | Fly.io secrets (GOOGLE_AI_STUDIO_API_KEY) |
| Models | gemini-2.0-flash, gemini-2.0-flash-lite | MODEL_* env vars |
| Chunk Size | 100 posts | config.py |
| SSE Keep-Alive | 5s + 2KB padding | Mobile stability fix |

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
3. **429 Quota errors** — Rotate to fresh API keys, check key validity at aistudio.google.com
