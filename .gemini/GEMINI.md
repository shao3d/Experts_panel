# Experts Panel: AI Context

**Last Updated:** 2026-03-28
**Status:** Production (Stable)
**Role:** System Architect & Explainer (MVP Principle)

## 🧠 Core Identity
You are working on **Experts Panel**, a RAG system analyzing Telegram & Reddit.
- **Stack:** Python 3.11 (FastAPI), React 18 (Vite/Tailwind), SQLite.
- **Architecture:** 8-phase Map-Resolve-Reduce pipeline.
- **Key Feature:** Parallel Reddit Sidecar Proxy (`experts-reddit-proxy`).

## 🗺️ Documentation Map (SSOT)
Use these files as your Source of Truth. Do NOT trust `plan_*.md` files in archive.

### 🏗️ Architecture
- **Pipeline Logic:** `docs/architecture/pipeline.md` (The Brain)
- **Hybrid Search:** `docs/architecture/super-passport-search.md` (Vector KNN + FTS5 + RRF)
- **Reddit Integration:** `docs/architecture/reddit-service.md` (The Sidecar)
- **Video Hub:** `docs/architecture/video-hub-service.md` (Digital Twin)
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
| **Drift** | `gemini-3-flash-preview` | `MODEL_DRIFT_ANALYSIS` |
| **AI Scout** | `gemini-3.1-flash-lite-preview` | `MODEL_SCOUT` |
| **Scoring** | `gemini-2.0-flash` | `MODEL_MEDIUM_SCORING` |
| **Embedding** | `gemini-embedding-001` | Hardcoded |
| **Video Twin** | `gemini-3-pro-preview` | `MODEL_VIDEO_PRO` |
| **Video Validation** | `gemini-3-flash-preview` | `MODEL_VIDEO_FLASH` |
| **Reddit** | Sidecar Proxy | `REDDIT_PROXY_URL` |

## 🚨 Operational Rules
1.  **Drift Analysis:** ALWAYS use `run_drift_service.py` (CLI wrapper) or `./scripts/update_production_db.sh`.
2.  **Expert Config:** ALWAYS update `frontend/src/config/expertConfig.ts` when adding experts.
3.  **Video Hub:** Ensure `topic_id` in JSON changes every 10-15 mins (logical chapters) for proper Summary Bridging context.
4.  **Reddit Proxy:** Do not modify `services/reddit-proxy` unless explicitly asked (it's a separate microservice).
5.  **No Hallucinations:** If a file is in `docs/archive/`, treat it as history, not current truth.

## 🛠️ Quick Commands
- **Start All:** `./quickstart.sh`
- **Deploy DB:** `./scripts/update_production_db.sh`
- **Deploy Video:** `./scripts/deploy_video.sh <json_path>`
- **Add Expert:** `./scripts/add_new_expert.sh <id> "<Name>" <user> <json>`
