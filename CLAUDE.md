# Experts Panel - Multi-Expert Query Processing System

Sophisticated 10-phase pipeline system for analyzing expert Telegram channels and synthesizing comprehensive answers using Google Gemini AI.

## 🚀 Quick Start (5 minutes)

For a guided setup, execute the `quickstart.sh` script in the project root. It handles dependency installation and configuration. After setup, the script will provide instructions to start the backend and frontend servers.

To verify the installation, check the health endpoint at `http://localhost:8000/health`. The API documentation for making queries is available at `http://localhost:8000/api/docs`.

## 🏗️ Architecture Overview

The system uses an advanced **ten-phase pipeline** for analysis and a hybrid, cost-optimized multi-model strategy. For a complete and up-to-date guide on the pipeline, data flow, and model strategy, please refer to the **[Pipeline Architecture Guide](docs/architecture/pipeline.md)**.

### Key Architectural Principles
- **Multi-Expert Architecture**: Complete data isolation between experts and parallel processing.
- **Embs&Keys Hybrid Search**: Multi-stage retrieval using Vector KNN (sqlite-vec) and FTS5 with Reciprocal Rank Fusion (RRF), eliminating Semantic Gaps with pre-computed vector embeddings.
- **Reddit MCP Integration**: Sidecar microservice for community insights with multi-strategy search, smart subreddit targeting, and 120s cold start timeout.
- **Cost Optimization**: Gemini-only strategy with Tier 1 paid account (high rate limits).
- **Real-time Progress**: SSE streaming with `pipeline_state` — aggregate phase tracking with Smart Grouping (Search, Analysis, Insights, Video, Synthesis, Reddit).
- **Search Toggles**: Optional `use_recent_only` (last 3 months), `include_reddit` (Reddit search), and `use_super_passport` (Embs&Keys Hybrid search) parameters.

## 📁 Component Documentation

### Backend Services & API
**📖 See: `backend/CLAUDE.md`**

Complete FastAPI backend with:
- Multi-expert query processing pipeline with parallel processing
- **Reddit MCP Integration**: Parallel pipeline for community insights with circuit breaker
- 11+ specialized services for different phases with Gemini integration
- Real-time SSE streaming for progress tracking with enhanced error handling
- Google AI Studio LLM integration (single-key with auto-retry)
- SQLite database with 10+ migration scripts (18MB active database)
- Production-ready Fly.io deployment with admin authentication
- Dynamic expert loading from database with expert metadata centralization

**Key Files:**
- `src/api/simplified_query_endpoint.py` - Main multi-expert query processing with parallel experts and Reddit pipeline (120s timeout)
- `src/api/admin_endpoints.py` - Admin authentication and production configuration
- `src/services/map_service.py` - Content relevance detection with hybrid models
- `src/services/medium_scoring_service.py` - Advanced post reranking with cost optimization
- `src/services/reddit_service.py` - Legacy Reddit HTTP client with circuit breaker
- `src/services/reddit_enhanced_service.py` - **NEW:** Multi-strategy Reddit aggregator (parallel searches, smart subreddits)
- `src/services/reddit_synthesis_service.py` - Reddit community analysis with Gemini
- `src/services/meta_synthesis_service.py` - Cross-expert unified analysis (≥2 experts)
- `src/services/translation_service.py` - Hybrid translation service with Google Gemini
- `src/services/language_validation_service.py` - Language consistency validation
- `src/config.py` - Comprehensive hybrid model configuration management
- `src/utils/error_handler.py` - User-friendly error processing system

### Frontend React Application
**📖 See: `frontend/CLAUDE.md`**

React 18 + TypeScript frontend with:
- Real-time query progress with expert tracking
- **Pixel Office Engine** - Canvas-based animated office (desktop only, hidden on mobile)
- **Reddit Community Insights** - Community analysis display with markdown rendering
- Post selection and navigation system
- Answer display with source references
- Responsive design with Tailwind CSS v3
- **Vitest** test suite (55+ tests)

**Key Components:**
- `App.tsx` - Main application state management with React.lazy code splitting
- `PixelOffice.tsx` - Canvas pixel office with 4-room layout (42×15 grid), context-aware animations: read→lounge seats, type→PC desks, proportional mix with stagger (desktop, lazy-loaded)
- `ProgressSection.tsx` - Smart Grouping progress (dynamic groups from `pipeline_state`)
- `CommunityInsightsSection.tsx` - Reddit community analysis UI
- `ExpertResponse.tsx` - Answer rendering with sources
- `QueryForm.tsx` - User input form with Reddit toggle checkbox

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
For a detailed guide, see **[Add New Expert Playbook](docs/guides/add-expert.md)**.

### Adding New Video (Video Hub)
To import a video and deploy it to production:
```bash
./scripts/deploy_video.sh <json_path>
```
See **[Video Hub Playbook](docs/guides/video-hub-operator.md)** for prompts, JSON format, and merge workflows.

### Updating Production & Data
To synchronize all experts, run drift analysis, and deploy the updated database to production:
```bash
./scripts/update_production_db.sh
```
This "Cycle of Life" script handles (9 steps):
1.  **Backup**: Creates a local backup of `experts.db`.
2.  **Sync**: Incrementally fetches new posts and comments for **all** experts.
3.  **Migrations**: Applies pending database migrations (idempotent, marker-file tracked).
4.  **Vectorization**: Generates embeddings for new posts (`embed_posts.py --continuous`) for Hybrid Search.
5.  **Drift Analysis**: Analyzes new comments for topic drift using Gemini.
6.  **Check/Wake Machine**: Verifies Fly.io machine status and wakes it if needed.
7.  **Remote Backup**: Creates backup of remote database on server.
8.  **Upload Database**: Compresses and uploads the updated database to Fly.io.
9.  **Restart Application**: Restarts the app to load the new database.

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
- **AI Scout** (`MODEL_SCOUT`): `gemini-3.1-flash-lite-preview` - Entity-centric FTS5 query generation
- **Meta-Synthesis** (`MODEL_META_SYNTHESIS`): `gemini-3-flash-preview` - Cross-expert unified analysis (≥2 experts)
- **Video Synthesis** (`MODEL_VIDEO_PRO`): `gemini-3-pro-preview` - Video Hub Digital Twin analysis
- **Video Validation** (`MODEL_VIDEO_FLASH`): `gemini-3-flash-preview` - Video Hub language validation

**Note:** The `gemini-3-flash-preview` model (released January 2026) provides significantly improved reasoning capabilities while maintaining high speed and cost efficiency compared to earlier Gemini models.

### Date Filtering (use_recent_only)
The system supports filtering queries to only use recent data (last 3 months):

- **API Parameter**: `use_recent_only: bool` in `QueryRequest`
- **Behavior**: When `true`, only posts and comments from the last 3 months are used
- **UI**: Checkbox "🕒 Только последние 3 месяца" in the query form
- **Implementation**: 
  - Posts filtered by `created_at >= cutoff_date` in endpoint
  - Linked posts filtered in `SimpleResolveService`
  - Drift groups filtered in `CommentGroupMapService`
  - Cutoff date calculated as 3 months ago using `get_cutoff_date()` utility

**Use cases:**
- **OFF (default)**: All data for comprehensive answers, methodology, historical context
- **ON**: Recent data only for fresh news, current models, faster processing

### Implementing New Features (Code Writer Agent)
For implementing new features, use the custom **implementer** agent — a Sonnet-based code writer pre-configured with all project patterns, conventions, and anti-overengineering rules.

**How to run:**
```bash
# With a plan file
claude --agent implementer "Реализуй план из ~/.claude/plans/<plan-file>.md"

# With a spec description
claude --agent implementer "Реализуй: <описание фичи>"

# With a spec file
claude --agent implementer "Реализуй спецификацию из docs/specs/<spec>.md"
```

**What it does:** Runs Claude Sonnet with project-specific system prompt (`.claude/agents/implementer.md`) + full `CLAUDE.md` context. The agent knows backend service patterns, frontend component patterns, config management, SSE pipeline, and has strict anti-overengineering rules.

**Agent memory:** Accumulates project knowledge across sessions in `.claude/agent-memory/implementer/`.

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
- **Documentation Map & Update Checklist**: `docs/DOCUMENTATION_MAP.md` - Index of all docs + checklist: which docs to update when code changes

### Configuration
- **Model Configuration**: `backend/src/config.py` - Environment variables and defaults
- **Database Schema**: `backend/src/models/` - SQLAlchemy models and relationships

### Development Tools
- **Prompts**: `backend/prompts/` - LLM prompts for each pipeline phase
- **Migrations**: `backend/migrations/` - Database evolution scripts
- **Scripts**: `backend/scripts/` - 30+ drift analysis and maintenance utilities
- **Asset Pipeline**: `scripts/copy-pixel-assets.sh` - Clones pixel-agents repo, copies sprites/layouts
- **Tests**: `frontend/vitest.config.ts` - Vitest test suite, run with `npm test` in frontend/

### Documentation Rules
**IMPORTANT**: When modifying code, consult `docs/DOCUMENTATION_MAP.md` section "Чеклист обновления документации" to determine which docs need updating. Key mappings:
- **Changed models (MODEL_*)**: Update `CLAUDE.md`, `backend/CLAUDE.md`, `docs/architecture/pipeline.md`, `.env.example`
- **Added/removed pipeline phase**: Update `docs/architecture/pipeline.md`, `CLAUDE.md`, `backend/CLAUDE.md`
- **Changed update_production_db.sh**: Update `CLAUDE.md` ("Cycle of Life" section)
- **Deleted any file**: `grep` all `.md` files for references to deleted file

---

## Reddit Community Insights

**Overview:** Real-time Reddit community analysis integrated into expert queries

**Architecture:** Sidecar pattern - Reddit Proxy microservice (`experts-reddit-proxy.fly.dev`)

**Key Features:**
- ✅ Parallel Reddit search with expert pipelines
- ✅ AI-powered community synthesis (Reality Check, Hacks & Workarounds, Vibe Check)
- ✅ Automatic query translation (RU → EN) for better Reddit search results
- ✅ Multi-language synthesis (responses in query language)
- ✅ Source attribution with direct Reddit links
- ✅ Circuit breaker pattern for reliability
- ✅ User-toggleable (Искать на Reddit checkbox, default: enabled)

**Components:**
- `RedditService` - HTTP client with retry logic, 15s timeout, 3 attempts
- `RedditSynthesisService` - Gemini-powered community analysis with language detection
- `TranslationService` - Query translation for non-English searches
- `CommunityInsightsSection` - React component with neutral styling
- Reddit Proxy - Node.js/Fastify microservice on Fly.io

**Fail-Safe Design:**
- Expert responses returned even if Reddit fails/times out
- 120s timeout for Reddit after experts complete
- Keep-alive SSE events (2.5s) during Reddit processing

---

**Project Status:** Production-ready with active development
**Last Updated:** 2026-03-31
**Architecture:** Multi-expert, Gemini-only LLM pipeline with unified client and real-time progress tracking
**Key Features:** Parallel expert processing, unified `google_ai_studio_client`, cost optimization with Gemini 3 Flash, language validation, comment synthesis, enhanced error handling, admin authentication, Reddit community insights, Pixel Office Engine (4-room Canvas office with CSS scaling)
**Change History:** See `git log` for detailed history of all changes.