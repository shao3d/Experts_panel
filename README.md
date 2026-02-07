# Experts Panel

[![CI/CD](https://github.com/andreysazonov/Experts_panel/workflows/CI%2FCD/badge.svg)](https://github.com/andreysazonov/Experts_panel/actions)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11+-blue.svg)](https://python.org)

**Intelligent system for analyzing expert Telegram channels and Reddit communities using Google Gemini AI**

Experts Panel is a powerful tool for semantic search and analysis of content from expert Telegram channels and Reddit communities. The system uses an advanced **8-phase Map-Resolve-Reduce pipeline architecture** with Google Gemini AI (2.5 Flash Lite & 3 Flash Preview) to provide accurate and contextually relevant answers.

## 🏗️ System Architecture

The system uses an advanced **eight-phase pipeline** to provide accurate and contextually relevant answers. The architecture includes cost-optimized Gemini-only strategy, differential processing for posts based on relevance, and parallel pipelines for content and comment analysis.

For a detailed breakdown of the 8-phase pipeline, component responsibilities, data flow, and model strategy, please see the **[Pipeline Architecture Guide](docs/pipeline-architecture.md)**.

### Models Strategy (Gemini Only)
- **Map Phase**: Gemini 2.5 Flash Lite (Speed & Instruction Following)
- **Synthesis/Reduce**: Gemini 3 Flash Preview (Reasoning)
- **Validation/Analysis**: Gemini 2.0 Flash (Speed)

## ✨ Key Features

- **🧠 8-phase Map-Resolve-Reduce Architecture**: Advanced pipeline with differential HIGH/MEDIUM posts processing
- **🎯 Cost-Optimized Gemini Strategy**: Google AI Studio with Tier 1 account (high rate limits)
- **🔍 Smart Semantic Search**: Finds relevant posts by meaning, not keywords
- **📊 Medium Posts Reranking**: Gemini-based scoring system with threshold ≥0.7 and top-5 selection
- **💬 Comment Groups & Synthesis**: Gemini pipeline for comment drift analysis and insights extraction
- **🌐 Language Validation**: Response language validation and translation when needed
- **⚡ Real-time**: Processing progress display via Server-Sent Events with error handling
- **👥 Multi-expert Support**: Complete data isolation with `expert_id` and parallel processing
- **🕒 Date Filtering**: Optional `use_recent_only` filter for last 3 months of data
- **👽 Reddit Integration**: Parallel analysis of technical subreddits with smart query expansion and ranking
- **🔒 Production Ready**: Admin authentication, security hardening with API key masking and robust error handling

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

- [Pipeline Architecture](docs/pipeline-architecture.md) - **The Source of Truth** for the 8-phase pipeline.
- [Backend Guide](backend/CLAUDE.md) - Services, Config, and API details.
- [Frontend Guide](frontend/CLAUDE.md) - React components and SSE integration.
- [Reddit Integration](docs/pipeline-architecture.md#reddit-pipeline-parallel) - Details on smart targeting and ranking.

## 🤝 Contributing

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
