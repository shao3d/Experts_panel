# Experts Panel: AI Context

**Last Updated:** 2026-02-16
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
- **Reddit Integration:** `docs/architecture/reddit-service.md` (The Sidecar)
- **Backend Services:** `backend/CLAUDE.md` (Service mapping)
- **Frontend Components:** `frontend/CLAUDE.md` (UI structure)

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
| **Scoring** | `gemini-2.0-flash` | `MODEL_MEDIUM_SCORING` |
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
