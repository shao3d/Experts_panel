# Experts Panel: AI Context

**Last Updated:** 2026-05-04
**Status:** Production (Stable)
**Role:** System Architect & Explainer (MVP Principle)

## 🧠 Core Identity
You are working on **Experts Panel**, a RAG system analyzing Telegram, Reddit, and long-form video transcripts.
- **Stack:** Python 3.11 (FastAPI), React 18 (Vite/Tailwind), SQLite.
- **Architecture:** 10-phase pipeline with Hybrid Retrieval, Reddit Sidecar, Video Hub, and Meta-Synthesis.
- **Key Features:** Parallel Reddit Sidecar Proxy (`experts-reddit-proxy`) and Video Hub "Digital Twin".

## 🗺️ Documentation Map (SSOT)
Use these files as your Source of Truth. Do NOT trust `plan_*.md` files in archive.

### 🏗️ Architecture
- **Pipeline Logic:** `docs/architecture/pipeline.md` (The Brain)
- **Hybrid Search:** `docs/architecture/super-passport-search.md` (Vector KNN + FTS5 + RRF)
- **Reddit Integration:** `docs/architecture/reddit-service.md` (The Sidecar)
- **Video Hub:** `docs/architecture/video-hub-service.md` (Digital Twin)
- **Current Expert Roster:** `docs/architecture/current-expert-roster.md` (active experts, removed experts, Fly volume caveat)
- **Backend Services:** `backend/CLAUDE.md` (Service mapping)
- **Frontend Components:** `frontend/CLAUDE.md` (UI structure)
- **Doc Update Rules:** `docs/DOCUMENTATION_MAP.md` (Чеклист обновления)

### 📘 Guides & Workflows
- **Add New Expert:** `docs/guides/add-expert.md`
- **Video Hub Playbook:** `docs/guides/video-hub-operator.md`
- **Semantic Chunking:** `docs/guides/semantic-chunking.md`
- **Drift Analysis:** `docs/guides/drift-analysis.md`

## ⚙️ Critical Configuration
| Component | Model / Setting | Env Var |
|-----------|----------------|---------|
| **Map Phase** | `gemini-2.5-flash-lite` | `MODEL_MAP` |
| **Synthesis** | `gemini-3-flash-preview` | `MODEL_SYNTHESIS` |
| **Validation** | `gemini-2.5-flash` | `MODEL_ANALYSIS` |
| **Comment Groups** | `gemini-2.5-flash` | `MODEL_COMMENT_GROUPS` |
| **Drift** | `gemini-3-flash-preview` | `MODEL_DRIFT_ANALYSIS` |
| **AI Scout** | `gemini-3.1-flash-lite-preview` | `MODEL_SCOUT` |
| **Scoring** | `gemini-2.5-flash` | `MODEL_MEDIUM_SCORING` |
| **Meta-Synthesis** | `gemini-3-flash-preview` | `MODEL_META_SYNTHESIS` |
| **Embedding** | `gemini-embedding-001` | `MODEL_EMBEDDING` |
| **Video Twin** | `gemini-3.1-pro-preview` | `MODEL_VIDEO_PRO` |
| **Video Validation** | `gemini-3-flash-preview` | `MODEL_VIDEO_FLASH` |
| **Reddit Proxy** | `https://experts-reddit-proxy.fly.dev` | Hardcoded in Reddit services |

## 🚨 Operational Rules
1.  **Drift Analysis:** ALWAYS use `run_drift_service.py` (CLI wrapper) or `./scripts/update_production_db.sh`.
2.  **Expert Roster:** ALWAYS update `frontend/src/config/expertConfig.ts` and `docs/architecture/current-expert-roster.md` when adding/removing experts; update Fly SQLite volume separately from code deploy.
3.  **Video Hub:** Ensure `topic_id` in JSON changes every 10-15 mins (logical chapters) for proper Summary Bridging context.
4.  **Reddit Proxy:** Do not modify `services/reddit-proxy` unless explicitly asked (it's a separate microservice).
5.  **No Hallucinations:** If a file is in `docs/archive/`, treat it as history, not current truth.

## 🛠️ Quick Commands
- **Start All:** `./quickstart.sh`
- **Deploy DB:** `./scripts/update_production_db.sh` (staged upload to `/app/data/experts.db.tmp`, then replace `/app/data/experts.db`)
- **Deploy Video:** `./scripts/deploy_video.sh <json_path>`
- **Add Expert:** `./scripts/add_new_expert.sh <id> "<Name>" <user> <json>`
