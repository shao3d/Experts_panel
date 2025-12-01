# Project Context: Experts Panel

**Last Updated:** 2025-11-27
**Status:** Production (v55)

## 🎯 Core Functionality
Multi-expert RAG system processing Telegram channels via an 8-phase pipeline (Map-Resolve-Reduce).
Key feature: **Listwise LLM Reranking** (Map phase) without Vector DB.

## 🏗️ Architecture Highlights
- **Stack:** FastAPI (Backend), React (Frontend), SQLite (DB), Fly.io (Hosting).
- **Streaming:** Server-Sent Events (SSE) for real-time progress.
- **LLM Strategy:** Hybrid (Google Gemini 2.0 Flash Free Tier -> OpenRouter Qwen Fallback).

## 🔧 Key Configurations (Critical)
- **Google AI Studio:**
  - **Aggressive Key Rotation:** Rotates on ANY rate limit (RPM/Daily).
  - **Keys:** 5 keys configured in Fly.io secrets (comma-separated).
  - **Chunk Size:** `100` posts (optimized for Gemini 1M context).
  - **Retry:** Map phase waits 90s if all keys exhausted.
- **Mobile Stability:**
  - SSE Keep-Alive interval: **5 seconds**.
  - Padding: **2KB** (to flush mobile proxy buffers).

## 📂 Documentation Map
- **Overview:** `CLAUDE.md`
- **Deep Dive:** `docs/pipeline-architecture.md`
- **Setup:** `README.md`

## 🚀 Deployment
- **Platform:** Fly.io
- **Auto-deploy:** GitHub Actions
- **Secrets:** `fly secrets set ...`

## 📝 Recent Changes
1.  Implemented aggressive key rotation for Google AI Studio.
2.  Increased Map Phase chunk size to 100.
3.  Added robust SSE Keep-Alive (5s + padding) to fix "Load failed" on mobile.
4.  **Automated Production Update:** Implemented `scripts/update_production_db.sh` for one-click Sync + Drift Analysis + Deploy.
5.  **Drift Analysis Integration:** Restored and automated `DriftSchedulerService` to analyze new comments before deployment.
6.  **Deployment Optimization:** Added Gzip compression for database uploads, significantly reducing deployment time.

