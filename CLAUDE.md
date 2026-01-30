@sessions/CLAUDE.sessions.md

# Experts Panel - Multi-Expert Query Processing System

Sophisticated 8-phase pipeline system for analyzing expert Telegram channels and synthesizing comprehensive answers using Google Gemini AI.

## 🚀 Quick Start (5 minutes)

For a guided setup, execute the `quickstart.sh` script in the project root. It handles dependency installation and configuration. After setup, the script will provide instructions to start the backend and frontend servers.

To verify the installation, check the health endpoint at `http://localhost:8000/health`. The API documentation for making queries is available at `http://localhost:8000/api/docs`.

## 🏗️ Architecture Overview

The system uses an advanced **eight-phase pipeline** for analysis and a hybrid, cost-optimized multi-model strategy. For a complete and up-to-date guide on the pipeline, data flow, and model strategy, please refer to the **[Pipeline Architecture Guide](docs/pipeline-architecture.md)**.

### Key Architectural Principles
- **Multi-Expert Architecture**: Complete data isolation between experts and parallel processing.
- **Cost Optimization**: Gemini-only strategy with Tier 1 paid account (high rate limits).
- **Real-time Progress**: SSE streaming for frontend progress tracking.

## 📁 Component Documentation

### Backend Services & API
**📖 See: `backend/CLAUDE.md`**

Complete FastAPI backend with:
- Multi-expert query processing pipeline with parallel processing
- 9+ specialized services for different phases with Gemini integration
- Real-time SSE streaming for progress tracking with enhanced error handling
- Google AI Studio LLM integration (single-key with auto-retry)
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
To add a new expert, use the automated script:
```bash
./scripts/add_new_expert.sh <expert_id> "<Name>" <username> <json_path>
```
This script handles registration, post import, full comment sync, and prepares drift analysis automatically. It will prompt you to run the production update script at the end.
For a detailed guide, see **[Add New Expert Playbook](docs/add-new-expert-playbook.md)**.

### Updating Production & Data
To synchronize all experts, run drift analysis, and deploy the updated database to production:
```bash
./scripts/update_production_db.sh
```
This "Cycle of Life" script handles:
1.  **Backup**: Creates a local backup of `experts.db`.
2.  **Sync**: Incrementally fetches new posts and comments for **all** experts.
3.  **Drift Analysis**: Analyzes new comments for topic drift using Gemini.
4.  **Deploy**: Compresses and uploads the database to Fly.io, then restarts the app.

### Database Operations
For interactive database management (e.g., initializing, resetting, or listing tables), use the script at `backend/src/models/database`. Database backups and migrations can be performed using standard `sqlite3` CLI commands, pointing to the database file at `backend/data/experts.db`. Migration scripts are located in `backend/migrations/`.

### Model Configuration
Model configuration is managed via environment variables as defined in `.env.example`. Do not modify model settings directly in the code.

**Current Production Models:**
- **Map Phase** (`MODEL_MAP`): `gemini-2.5-flash-lite` - Ultra-fast relevance detection
- **Synthesis Phases** (`MODEL_SYNTHESIS`): `gemini-3-flash-preview` - Pro-grade reasoning for quality synthesis
- **Analysis Tasks** (`MODEL_ANALYSIS`): `gemini-2.0-flash` - Fast, reliable for translation/validation
- **Medium Scoring** (`MODEL_MEDIUM_SCORING`): `gemini-2.0-flash` - Content scoring
- **Comment Groups** (`MODEL_COMMENT_GROUPS`): `gemini-2.0-flash` - Comment relevance
- **Drift Analysis** (`MODEL_DRIFT_ANALYSIS`): `gemini-3-flash-preview` - Advanced topic drift detection

**Note:** The `gemini-3-flash-preview` model (released January 2026) provides significantly improved reasoning capabilities while maintaining high speed and cost efficiency compared to earlier Gemini models.

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
**Last Updated:** 2026-01-28
**Architecture:** Multi-expert, Gemini-only LLM pipeline with unified client and real-time progress tracking
**Key Features:** Parallel expert processing, unified `google_ai_studio_client`, cost optimization with Gemini 3 Flash, language validation, comment synthesis, enhanced error handling, admin authentication
**Recent Updates:**
- ✅ Added real-time stats (posts/comments) to expert selection UI
- ✅ Implemented collapsible expert selection bar for cleaner UX
- ✅ Added new experts: Ilia, Polyakov, Doronin
- ✅ Migrated to `gemini-2.5-flash-lite` for Map phase (ultra-fast)
- ✅ Upgraded to `gemini-3-flash-preview` for Synthesis and Drift Analysis (pro-grade reasoning)
- ✅ Unified all services to use `google_ai_studio_client.py` for consistent API access
- ✅ Removed hardcoded model defaults - all configuration via environment variables
- ✅ Added `MODEL_DRIFT_ANALYSIS` configuration for offline cron jobs