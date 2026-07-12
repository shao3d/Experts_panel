# Experts Panel

[![CI](https://github.com/shao3d/Experts_panel/actions/workflows/ci.yml/badge.svg)](https://github.com/shao3d/Experts_panel/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/) [![React 18](https://img.shields.io/badge/react-18-149eca.svg)](https://react.dev/)

**A source-grounded research system for comparing how practitioners think about AI and its application.**

Choose one or more experts, ask a question in English or Russian, and get an answer built from their actual published material rather than from a generic model persona. Experts Panel finds the relevant source fragments, analyzes each expert separately, and, when several experts are selected, produces a cross-expert synthesis without hiding disagreement.

[Open the live app](https://expa.beyondhorizon.dev/)

## What it does

- Searches curated expert corpora with hybrid retrieval: vector KNN, FTS5, and Reciprocal Rank Fusion.
- Runs a ten-phase Map-Resolve-Reduce pipeline for relevance scoring, source analysis, comment context, validation, and synthesis.
- Keeps each expert's evidence isolated before producing a multi-expert view.
- Adds optional Reddit research and a Video Hub source alongside Telegram material.
- Streams progress and results to the React interface over Server-Sent Events.
- Preserves source references so the result can be checked against the underlying material.

## More than the web interface

The project also contains two workflows built on the same evidence layer:

- **Panex** is an explicit agent-facing API and CLI. It lets an AI coding agent request a source-backed digest from selected experts and inspect the exact supporting sources when needed.
- **Expert admission control** uses semantic passports and a Knowledge Matrix to show current coverage, identify gaps or excessive overlap, and support a human decision before a new expert is added.

These are intentionally bounded tools. Panex retrieves and structures expert evidence; it does not impersonate an expert or make project decisions on their behalf. The Knowledge Matrix supports admission review; it is not an automatic judge.

## Architecture at a glance

- **Backend:** FastAPI, SQLAlchemy, SQLite/FTS5, Google Gemini through Vertex AI.
- **Frontend:** React 18, TypeScript, Vite, Tailwind CSS, TanStack Query.
- **Retrieval:** Gemini embeddings, vector KNN, full-text search, RRF, and AI-assisted query expansion.
- **Delivery:** SSE progress events plus durable result artifacts for long-running UI and agent requests.
- **Integrations:** Telegram ingestion, Reddit sidecar, Video Hub, and the Panex agent surface.

The detailed pipeline is documented in [Pipeline Architecture](docs/architecture/pipeline.md). Hybrid retrieval is covered in [Super Passport Search](docs/architecture/super-passport-search.md).

## Local development

Requirements:

- Python 3.11+
- Node.js 20+
- a Google Cloud project with Vertex AI enabled
- a local SQLite corpus

Set up the backend:

```bash
python3 -m venv backend/.venv
source backend/.venv/bin/activate
pip install -r backend/requirements.txt
cp .env.example backend/.env
```

Fill in the Vertex AI settings and `DATABASE_URL` in `backend/.env`, then start the API:

```bash
cd backend
uvicorn src.api.main:app --reload --port 8000
```

In a second terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

The frontend runs at `http://localhost:5173` and uses `http://localhost:8000` as the default development API.

The production corpus, Telegram sessions, service-account credentials, and other secrets are not part of this repository. Use `.env.example` as the configuration reference and import your own source data for a populated local instance.

## Checks

```bash
cd backend
python -m pytest
```

```bash
cd frontend
npm run test:run
npm run build
```

GitHub Actions also validates the backend, frontend build, and Docker configuration on pull requests and pushes to `main`.

## Technical documentation

- [Pipeline Architecture](docs/architecture/pipeline.md)
- [Hybrid Retrieval](docs/architecture/super-passport-search.md)
- [Panex Usage](docs/guides/panex-usage.md)
- [Agent Context API](docs/architecture/agent-context-api.md)
- [Expert Admission Control and Knowledge Matrix](docs/architecture/expert-admission-control.md)
- [Reddit Integration](docs/architecture/reddit-service.md)
- [Video Hub](docs/architecture/video-hub-service.md)

## License

This project is available under the [MIT License](LICENSE).
