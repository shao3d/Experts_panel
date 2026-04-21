# Experts Panel

[![CI/CD](https://github.com/andreysazonov/Experts_panel/workflows/CI%2FCD/badge.svg)](https://github.com/andreysazonov/Experts_panel/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/react-18-blue.svg)](https://reactjs.org)
[![Tailwind](https://img.shields.io/badge/tailwind-3-38bdf8.svg)](https://tailwindcss.com)

**Intelligent system for analyzing expert Telegram channels and Reddit communities using Google Gemini AI**

Experts Panel is a powerful tool for semantic search and analysis of content from expert Telegram channels and Reddit communities. The system uses an advanced **10-phase Map-Resolve-Reduce pipeline architecture** with Google Gemini on **Vertex AI** to provide accurate and contextually relevant answers.

## 🏗️ System Architecture

The system uses an advanced **ten-phase pipeline** to provide accurate and contextually relevant answers. The architecture includes a Gemini-only strategy on **Vertex AI**, differential processing for posts based on relevance, and parallel pipelines for content and comment analysis.

### Models Strategy (Gemini Only)
- **Map Phase**: Gemini 2.5 Flash Lite (Speed & Instruction Following)
- **Synthesis/Reduce**: Gemini 3 Flash Preview (Reasoning)
- **AI Scout**: Gemini 3.1 Flash Lite Preview
- **Validation/Analysis**: Gemini 2.5 Flash

### Runtime Notes
- **LLM Runtime**: Vertex AI with service-account authentication (`VERTEX_AI_SERVICE_ACCOUNT_JSON` or `VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH`)
- **Gemini 3 Routing**: All `Gemini 3*` models are routed via the **Vertex global endpoint**
- **Project-specific fallback**: This Vertex project does **not** expose `gemini-2.0-flash`, so analysis / medium scoring / comment groups run on `gemini-2.5-flash`

## ✨ Key Features

- **🎨 Modern UI**: Clean, responsive interface built with React, Tailwind CSS, and a collapsible Sidebar.
- **🧠 10-phase Map-Resolve-Reduce Architecture**: Advanced pipeline with differential HIGH/MEDIUM posts processing.
- **🎯 Cost-Optimized Gemini Strategy**: Vertex AI with service-account auth.
- **🔍 Smart Semantic Search**: Finds relevant posts by meaning using Hybrid Retrieval (Vector KNN + FTS5 + RRF).
- **📊 Medium Posts Reranking**: Gemini-based scoring system with threshold ≥0.7.
- **💬 Comment Groups & Synthesis**: Gemini pipeline for comment drift analysis.
- **⚡ Real-time**: Server-Sent Events (SSE) for instant progress updates.
- **👥 Multi-expert Support**: "Select All" groups, smart avatar initials, and complete data isolation.
- **🕒 Smart Filters**: "Embs&Keys" (Hybrid Search), "Recent Only" (3 months), and "Reddit Search" toggles directly in the Sidebar.
- **👽 Reddit Integration**: Parallel analysis via Sidecar Proxy (`experts-reddit-proxy`).
- **🚀 Reddit-Only Mode**: Bypass expert analysis for broad community searches.

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Google Cloud project with Vertex AI enabled
- Vertex AI service-account JSON or ADC-compatible credentials

For a guided setup experience, execute the `quickstart.sh` script located in the project root.

```bash
./quickstart.sh
```

For manual setup, copy `.env.example` to `backend/.env` and configure Vertex AI auth there:

```bash
cd backend
cp ../.env.example .env
```

Minimum required runtime variables:
- `VERTEX_AI_PROJECT_ID`
- `VERTEX_AI_LOCATION`
- `VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH` for local development
  or `VERTEX_AI_SERVICE_ACCOUNT_JSON` for managed environments

## 🧰 Maintenance Scripts

- `./scripts/update_production_db.sh`: loads `backend/.env`, runs sync, `backend/scripts/embed_posts.py --continuous`, and `backend/run_drift_service.py`. The embedding and drift steps use **Vertex AI**.
- `./scripts/deploy_video.sh <json_path>`: imports prepared video JSON into SQLite and deploys the database artifact. The script itself does **not** call Gemini directly.
- `python3 stress_test_gemini.py` and `python3 test_model.py`: standalone smoke tests that reuse the project's **Vertex AI** runtime from `backend/.env`.

## 📚 Documentation

- [Pipeline Architecture](docs/architecture/pipeline.md) - **The Source of Truth** for the 10-phase pipeline.
- [Frontend Guide](frontend/CLAUDE.md) - **NEW**: React + Tailwind architecture, Sidebar layout, and State management.
- [Backend Guide](backend/CLAUDE.md) - Services, Config, and API details.
- [Reddit Integration](docs/architecture/reddit-service.md) - Details on smart targeting and ranking.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
