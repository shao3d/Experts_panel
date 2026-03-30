# Experts Panel

[![CI/CD](https://github.com/andreysazonov/Experts_panel/workflows/CI%2FCD/badge.svg)](https://github.com/andreysazonov/Experts_panel/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)
[![React](https://img.shields.io/badge/react-18-blue.svg)](https://reactjs.org)
[![Tailwind](https://img.shields.io/badge/tailwind-3-38bdf8.svg)](https://tailwindcss.com)

**Intelligent system for analyzing expert Telegram channels and Reddit communities using Google Gemini AI**

Experts Panel is a powerful tool for semantic search and analysis of content from expert Telegram channels and Reddit communities. The system uses an advanced **10-phase Map-Resolve-Reduce pipeline architecture** with Google Gemini AI (2.5 Flash Lite & 3 Flash Preview) to provide accurate and contextually relevant answers.

## 🏗️ System Architecture

The system uses an advanced **ten-phase pipeline** to provide accurate and contextually relevant answers. The architecture includes cost-optimized Gemini-only strategy, differential processing for posts based on relevance, and parallel pipelines for content and comment analysis.

### Models Strategy (Gemini Only)
- **Map Phase**: Gemini 2.5 Flash Lite (Speed & Instruction Following)
- **Synthesis/Reduce**: Gemini 3 Flash Preview (Reasoning)
- **Validation/Analysis**: Gemini 2.0 Flash (Speed)

## ✨ Key Features

- **🎨 Modern UI**: Clean, responsive interface built with React, Tailwind CSS, and a collapsible Sidebar.
- **🧠 10-phase Map-Resolve-Reduce Architecture**: Advanced pipeline with differential HIGH/MEDIUM posts processing.
- **🎯 Cost-Optimized Gemini Strategy**: Google AI Studio with Tier 1 account (high rate limits).
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
- Google AI Studio API key(s)

For a guided setup experience, execute the `quickstart.sh` script located in the project root.

```bash
./quickstart.sh
```

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
