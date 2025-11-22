@sessions/CLAUDE.sessions.md

# Experts Panel - Multi-Expert Query Processing System

Sophisticated 7-phase pipeline system for analyzing expert Telegram channels and synthesizing comprehensive answers using multiple AI models.

## 🚀 Quick Start (5 minutes)

For a guided setup, execute the `quickstart.sh` script in the project root. It handles dependency installation and configuration. After setup, the script will provide instructions to start the backend and frontend servers.

To verify the installation, check the health endpoint at `http://localhost:8000/health`. The API documentation for making queries is available at `http://localhost:8000/api/docs`.

## 🏗️ Architecture Overview

The system uses an advanced **eight-phase pipeline** for analysis and a hybrid, cost-optimized multi-model strategy. For a complete and up-to-date guide on the pipeline, data flow, and model strategy, please refer to the **[Pipeline Architecture Guide](docs/pipeline-architecture.md)**.

### Key Architectural Principles
- **Multi-Expert Architecture**: Complete data isolation between experts and parallel processing.
- **Cost Optimization**: Utilizes a hybrid model system with free-tier Google models and automatic fallback to OpenRouter, plus automatic API key rotation.
- **Real-time Progress**: SSE streaming for frontend progress tracking.

## 📁 Component Documentation

### Backend Services & API
**📖 See: `backend/CLAUDE.md`**

Complete FastAPI backend with:
- Multi-expert query processing pipeline with parallel processing
- 9+ specialized services for different phases with hybrid model integration
- Real-time SSE streaming for progress tracking with enhanced error handling
- Hybrid multi-model LLM integration (OpenRouter + Google AI Studio) with cost optimization
- SQLite database with 10+ migration scripts (18MB active database)
- Production-ready Fly.io deployment with admin authentication
- Dynamic expert loading from database with expert metadata centralization

**Key Files:**
- `src/api/simplified_query_endpoint.py` - Main multi-expert query processing with parallel experts
- `src/api/admin_endpoints.py` - Admin authentication and production configuration
- `src/services/map_service.py` - Content relevance detection with hybrid models
- `src/services/medium_scoring_service.py` - Advanced post reranking with cost optimization
- `src/services/translation_service.py` - Hybrid translation service with Google Gemini
- `src/services/language_validation_service.py` - Language consistency validation
- `src/config.py` - Comprehensive hybrid model configuration management
- `src/utils/error_handler.py` - User-friendly error processing system

### Frontend React Application
**📖 See: `frontend/CLAUDE.md`**

React 18 + TypeScript frontend with:
- Real-time query progress with expert tracking
- Post selection and navigation system
- Answer display with source references
- Advanced debug logging system
- Responsive design with inline styles

**Key Components:**
- `App.tsx` - Main application state management
- `ProgressSection.tsx` - Enhanced progress display
- `ExpertResponse.tsx` - Answer rendering with sources

### Database & Data Management
**Location:** `backend/data/experts.db` (18MB active database)

- **Posts**: Expert channel content with metadata and expert isolation
- **Comments**: Hierarchical comment structure with expert associations
- **Links**: Post relationships and connections (depth 1 only)
- **Experts**: Centralized expert metadata with display names and channel usernames
- **Expert Isolation**: Complete data separation by expert_id
- **Migration Scripts**: 10+ database evolution scripts in `backend/migrations/`
- **Drift Analysis**: Comprehensive comment drift analysis and topic tracking

## 🔧 Common Development Tasks

### Adding New Expert
To add a new expert, use the data import script located at `backend/src/data/json_parser.py`. After import, you can verify the new expert has been added using the interactive database management script at `backend/src/models/database`.

### Database Operations
For interactive database management (e.g., initializing, resetting, or listing tables), use the script at `backend/src/models/database`. Database backups and migrations can be performed using standard `sqlite3` CLI commands, pointing to the database file at `backend/data/experts.db`. Migration scripts are located in `backend/migrations/`.

### Model Configuration
Model configuration is managed via environment variables as defined in `.env.example`. Do not modify model settings directly in the code.

### Testing Pipeline
To test the pipeline, use the interactive API documentation (available at `/api/docs` when the server is running) to send requests to the `/api/v1/query` endpoint. You can test the entire pipeline or filter for specific experts. Individual posts can also be retrieved via the `/api/v1/posts/{post_id}` endpoint.

## 🚀 Production Deployment

The application is configured for deployment on Fly.io using the `fly.toml` file.

To deploy, use the Fly.io CLI (`flyctl`) and set the required secrets as defined in `.env.example`. For detailed instructions, please refer to the official Fly.io documentation.

The `backend/CLAUDE.md` file also contains a more detailed guide specific to this project's production deployment.

## 🔍 Troubleshooting

### Server Issues
To check the backend health, access the `/health` endpoint. To verify the frontend is running, check its configured port (e.g., `http://localhost:3000`).

Logs are the primary source for debugging. The log file locations are configured via environment variables (see `.env.example`) and default to `backend/data/backend.log` and `backend/data/frontend.log`.

### Common Problems
- **Port conflicts**: The backend defaults to port 8000 and the frontend to 3000.
- **Environment variables**: Ensure `.env` exists and contains the required API keys.
- **Database location**: The active database is at `backend/data/experts.db`.
- **Model configuration**: The model strategy is defined by environment variables in `.env.example` and implemented in `backend/src/config.py`.
- **Production deployment**: For Fly.io deployments, ensure all required secrets are set correctly using `fly secrets list`.

### Debug Commands
To debug the pipeline, monitor the backend log file for messages containing specific identifiers:
- **Expert Processing**: Look for messages containing the relevant `expert_id`.
- **Pipeline Phases**: Search for messages containing `phase` and `complete` to track progress.
- **Frontend Events**: The frontend log contains events for API calls and SSE messages; search for terms like `api` and `query`.

## 📚 Additional Documentation

### Component Guides
- **Backend Architecture**: `backend/CLAUDE.md` - Complete API and services reference
- **Frontend Development**: `frontend/CLAUDE.md` - React components and UI patterns

### Configuration
- **Model Configuration**: `backend/src/config.py` - Environment variables and defaults
- **Database Schema**: `backend/src/models/` - SQLAlchemy models and relationships

### Development Tools
- **Prompts**: `backend/prompts/` - LLM prompts for each pipeline phase
- **Migrations**: `backend/migrations/` - Database evolution scripts
- **Scripts**: `backend/scripts/` - 30+ drift analysis and maintenance utilities

---

**Project Status:** Production-ready with active development
**Last Updated:** 2025-11-22
**Architecture:** Multi-expert, hybrid multi-model LLM pipeline with cost optimization and real-time progress tracking
**Key Features:** Parallel expert processing, hybrid model fallback system, cost optimization with Google AI Studio, language validation, comment synthesis, enhanced error handling, admin authentication