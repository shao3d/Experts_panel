
@sessions/CLAUDE.sessions.md

# Experts Panel Development Guidelines

Auto-generated from feature plans. Last updated: 2025-11-01

## Active Technologies
- Python 3.11+ with FastAPI and Pydantic v2
- SQLite with SQLAlchemy 2.0
- React 18 with TypeScript
- OpenRouter API - Multi-model strategy:
  - Qwen 2.5-72B Instruct for Map phase, Medium Scoring, Translation, Language Validation, and Comment Groups (configurable via MODEL_ANALYSIS)
  - Gemini 2.0 Flash for Reduce and Comment Synthesis
- Docker for development and production deployment
- Production-ready Fly.io cloud hosting with automated deployment

## Project Structure
```
backend/
├── src/
│   ├── models/       # SQLAlchemy models
│   ├── services/     # Map-Resolve-Reduce pipeline and utilities
│   ├── api/          # FastAPI endpoints
│   ├── data/         # Import and parsing
│   └── utils/        # Utility functions and helpers
│       ├── entities_converter.py  # Telegram entities to markdown converter
│       └── language_utils.py      # Language detection and validation utilities
├── prompts/          # LLM prompts (optimized per model)
├── migrations/       # Database migrations
└── tests/            # Validation queries

frontend/
├── src/
│   ├── components/   # React components
│   ├── services/     # API client with SSE streaming
│   └── types/        # TypeScript interfaces
└── public/           # Static assets

data/                    # Data directory at project root
└── experts.db           # SQLite database (working database with data)

# Database Locations
# Primary database: data/experts.db (project root)
# Secondary: backend/data/experts.db (may exist during development)

# Backend Root Scripts

## Core Pipeline Scripts
├── sync_channel.py                    # Telegram channel synchronization
├── sync_channel_multi_expert.py       # Multi-expert synchronization
├── import_interactive.py              # Interactive data import
├── populate_test_data.py              # Test data generation
├── run_import.py                      # Batch import runner

## Drift Analysis Scripts
├── analyze_drift.py                   # Comment drift analysis (main script)
├── fix_drift_topics.py                # Fix drift topics in database
├── fix_double_nested_drift.py         # Fix double nested drift issues
├── refill_drift_topics.py             # Refill drift topics for posts
├── run_drift_on_synced.py             # Run drift analysis on synced data
├── analyze_specific_drift.py          # Analyze specific drift patterns
├── run_single_drift_analysis.py       # Run drift analysis for single post
├── custom_drift_analysis_680.py       # Custom drift analysis for post 680
├── drift_on_synced_single.py          # Single post drift analysis

## Post-Specific Drift Analysis Scripts
├── analyze_drift_140.py               # Drift analysis for post 140
├── analyze_drift_696.py               # Drift analysis for post 696
├── analyze_drift_post_716.py          # Drift analysis for post 716
├── analyze_drift_post_720.py          # Drift analysis for post 720
├── run_drift_on_synced_673.py         # Run drift on synced post 673
├── run_drift_on_synced_695.py         # Run drift on synced post 695
├── run_drift_on_synced_specific.py    # Run drift on specific synced posts

## PostgreSQL Migration Scripts
├── apply_postgres_migrations.py       # PostgreSQL migrations
├── sync_to_postgres.py                # Sync to PostgreSQL

## Testing Scripts
├── test_hybrid_llm.py                 # Test hybrid LLM configuration
├── test_hybrid_simple.py              # Simple hybrid LLM testing

# Project Test Files
tests/
├── test_queries.py                    # Query validation tests (at project root)
├── test_queries.json                  # Test query data and expected results
backend/tests/
├── validation/
│   └── performance_test.py            # Performance tests

quickstart_validate.py                 # Quick validation script

# Fly.io Configuration
fly.toml              # Fly.io app configuration
Dockerfile            # Multi-stage build for Fly.io deployment
```

## 🗺️ Key Documentation References

### Core Architecture
- **Pipeline Architecture**: `/docs/pipeline-architecture.md` 🚀
- **Multi-Expert Setup**: `/docs/multi-expert-guide.md` 👥
- **Fly.io Deployment**: See configuration below ✈️

### Quick Reference
- **Database Operations**: See `models/database.py`
- **API Endpoints**: See `api/simplified_query_endpoint.py`
- **Import Scripts**: See `data/json_parser.py`
- **Medium Scoring**: See `services/medium_scoring_service.py`
- **Language Validation**: See `services/language_validation_service.py`

## 🔍 Log Access (for Claude Development)

### Development Log Files
- **Backend Log**: `backend/backend.log` - Main FastAPI/Uvicorn logs with request tracking
- **Frontend Log**: `frontend.log` - Vite development server logs
- **Session Logs**: `sessions/mode-revert-debug.log` - Claude sessions debug logs

### Quick Log Commands
```bash
# Watch logs in real-time
tail -f backend/backend.log          # Backend logs (API requests, pipeline phases)
tail -f frontend.log                 # Frontend logs (Vite, builds)

# Find recent errors
grep -i "error\|exception\|failed" backend/backend.log | tail -10

# Find recent query processing
grep -i "query\|processing" backend/backend.log | tail -5

# Check server status
curl -s http://localhost:8000/health | jq '.'    # Backend health
curl -s http://localhost:5173 > /dev/null && echo "Frontend OK" || echo "Frontend down"

# Find specific expert processing
grep "expert_id" backend/backend.log | tail -10
```

### Production Logs (Fly.io)
```bash
fly logs                           # All production logs
fly logs --grep "ERROR"            # Production errors only
fly logs --since 1h                # Last hour of logs
```

### Log Content Examples
- **Backend**: Request IDs, pipeline phases (map/resolve/reduce), expert processing, API errors
- **Frontend**: Vite server startup, build progress, port information
- **Session**: Claude session state changes, mode switches

## Commands

### Backend Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (ONLY way that works!)
cd backend && python3 -m uvicorn src.api.main:app --reload --port 8000

# Database management
python -m src.models.database  # Interactive DB operations (init/reset/drop)

# Import Telegram data (multi-expert support)
python -m src.data.json_parser <json_file> --expert-id <expert_id>

# Add comments interactively
python -m src.data.comment_collector

# Drift analysis (Pipeline B pre-processing)
cd backend && python analyze_drift.py
# ⚠️ MUST re-run after data reimport

# Telegram channel synchronization
cd backend && python sync_channel.py --dry-run --expert-id <expert_id>
cd backend && python sync_channel.py --expert-id <expert_id>
/sync  # Alternative: use slash command
```

### Frontend Development
```bash
# Install dependencies
npm install

# Run development server
npm run dev

# Build for production
npm run build

# Type checking
npm run type-check
```

### Database Management
```bash
# Create database (run from backend directory)
cd backend && sqlite3 data/experts.db < schema.sql

# Run migrations (apply in order from backend directory)
# Note: There are two files numbered 006 and 007 - apply both as needed
cd backend && sqlite3 data/experts.db < migrations/001_create_comment_group_drift.sql
cd backend && sqlite3 data/experts.db < migrations/002_add_sync_state.sql
cd backend && sqlite3 data/experts.db < migrations/003_add_expert_id.sql
cd backend && sqlite3 data/experts.db < migrations/004_add_expert_id_to_drift.sql
cd backend && sqlite3 data/experts.db < migrations/005_add_unique_telegram_message_id.sql
cd backend && sqlite3 data/experts.db < migrations/006_add_unique_telegram_message_id.sql
cd backend && sqlite3 data/experts.db < migrations/007_fix_unique_telegram_message_id.sql
cd backend && sqlite3 data/experts.db < migrations/007_add_channel_username.sql
cd backend && sqlite3 data/experts.db < migrations/008_fix_comment_unique_constraint.sql

# Backup database (run from backend directory)
cd backend && sqlite3 data/experts.db ".backup data/backup.db"

# Query drift groups (run from backend directory)
cd backend && sqlite3 data/experts.db "SELECT post_id, has_drift, analyzed_at FROM comment_group_drift WHERE has_drift=1;"
```

## 🚀 Production Deployment (Fly.io)

### Prerequisites
- Fly.io account with `flyctl` installed
- OpenRouter API key
- Latest `experts.db` database file

### Quick Production Deployment (5 minutes)
```bash
# 1. Install Fly CLI
curl -L https://fly.io/install.sh | sh

# 2. Authenticate with Fly.io
fly auth login

# 3. Deploy Application
fly deploy

# 4. Set up secrets
fly secrets set OPENROUTER_API_KEY=your-key-here

# 5. Health check
curl https://experts-panel.fly.dev/health
```

### Production Management Commands
```bash
# Check deployment status
fly status

# View application logs
fly logs

# Deploy new version
fly deploy

# Open application in browser
fly open
```

### Production Architecture
- **Single Service**: Monolithic application with embedded frontend
- **SSL/HTTPS**: Automatic HTTPS termination by Fly.io
- **Database Persistence**: SQLite database mounted to persistent volume
- **Health Monitoring**: Built-in health checks and automatic restarts
- **Zero-downtime deployments**: Rolling deployments with instant rollback

## Code Style

### Python
- Use type hints for all functions
- Async functions for I/O operations
- Pydantic models for validation
- Clear docstrings for pipeline phases
- Descriptive error messages

### TypeScript
- Strict mode enabled
- Interface over type where possible
- Explicit return types
- Component props fully typed
- No any types

### SQL
- Foreign keys for all relationships
- Comments on complex queries
- Indexes on frequently queried columns
- Use transactions for multi-table operations

## 🏗️ Pipeline Overview

The system uses an **eight-phase pipeline** with hybrid Medium posts reranking and language validation:

1. **Map Phase** - Qwen 2.5-72B finds relevant posts (HIGH/MEDIUM/LOW classification)
2. **Medium Scoring Phase** - Qwen 2.5-72B scores Medium posts (≥0.7 threshold → top-5 selection) ✅
3. **Differential Resolve Phase** -
   - HIGH posts → processed with linked posts (depth 1) via Resolve phase
   - Selected Medium posts → bypass Resolve, go directly to Reduce phase
4. **Reduce Phase** - Gemini 2.0 Flash synthesizes answer with all selected posts
5. **Language Validation Phase** - Qwen 2.5-72B validates response language consistency with query language ✅
6. **Comment Groups** - Qwen 2.5-72B finds relevant comment discussions
7. **Comment Synthesis** - Gemini 2.0 Flash extracts complementary insights

*For detailed pipeline architecture see `/docs/pipeline-architecture.md`*

## 🔧 Environment Variables

### Model Configuration
- `MODEL_ANALYSIS` - Analysis model for Map, Medium Scoring, Translation, Language Validation, and Comment Groups phases (default: qwen-2.5-72b)
  - Maximum quality: Set to `qwen/qwen-2.5-72b-instruct` for highest accuracy
  - **Bulletproof rollback**: Change this single variable to instantly switch ALL Qwen services

### Medium Posts Reranking
- `MEDIUM_SCORE_THRESHOLD` - Score threshold for Medium posts (default: 0.7)
- `MEDIUM_MAX_SELECTED_POSTS` - Maximum Medium posts to select (default: 5)
- `MEDIUM_MAX_POSTS` - Memory limit for Medium posts processing (default: 50)

### Required Variables
- `OPENROUTER_API_KEY` - OpenRouter API key for multi-model access

### Optional Variables
- `DATABASE_URL` - Database connection string (default: sqlite:///data/experts.db)
- `MAX_POSTS_LIMIT` - Maximum posts to process (default: 500)
- `CHUNK_SIZE` - Posts per processing chunk (default: 20)
- `REQUEST_TIMEOUT` - Request timeout in seconds (default: 300)

## 🚀 SERVER STARTUP GUIDE

### 📋 Prerequisites Check
Before starting servers, ensure:
- ✅ `.env` file exists in project root with `OPENROUTER_API_KEY`
- ✅ Python 3.11+ available (`python3 --version`)
- ✅ Node.js 18+ available (`node --version`)
- ✅ SQLite database path ready

### 🐍 Backend Server (Port 8000)
**ONLY Working Methods (choose one):**

**Method 1: Python3 (Recommended)**
```bash
cd backend && python3 -m uvicorn src.api.main:app --reload --port 8000
```

**Method 2: UV (if installed)**
```bash
cd backend && uv run uvicorn src.api.main:app --reload --port 8000
```

**✅ Success Indicators:**
- Server starts on http://127.0.0.1:8000
- Database tables verified/created message
- Health endpoint: http://localhost:8000/health
- Response: `{"status":"healthy","database":"healthy","openrouter_configured":true}`

**❌ DOES NOT WORK:**
- `source .env && python3...` - Environment loading issues
- `export $(cat .env) && python3...` - Variable expansion problems
- `python3 src/api/main.py` - Direct import issues

### ⚛️ Frontend Server (Port 5173)
**Start Method:**
```bash
cd frontend && npm run dev
```

**✅ Success Indicators:**
- Vite server starts (default port 5173, may vary if occupied)
- Page loads: http://localhost:5173/ (or other available port)
- Hot reload enabled for development
- Title: "Experts Panel - Telegram Channel Analyzer"

### 🔧 Complete Development Setup
**Start Both Servers:**
```bash
# Terminal 1: Backend
cd backend && python3 -m uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Frontend
cd frontend && npm run dev
```

**Access Points:**
- 🌐 Frontend: http://localhost:5173/ (or port shown in terminal)
- 🔧 Backend API: http://localhost:8000/
- ❤️ Health Check: http://localhost:8000/health
- 📖 API Docs: http://localhost:8000/docs

### 🚨 Troubleshooting
**Backend Issues:**
- Check `.env` file exists in project root
- Verify `OPENROUTER_API_KEY` is set
- Ensure port 8000 is not occupied
- Use `python3` not `python` command

**Frontend Issues:**
- Run `npm install` if dependencies missing
- Check if port 5173 (or shown port) is available
- Verify backend is running first (API connection)

### API Testing:
```bash
# Query all experts (default)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Your question", "stream_progress": false}' \
  -o /tmp/result.json

# Query specific expert
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Your question", "expert_filter": ["refat"], "stream_progress": false}' \
  -o /tmp/result.json
```

## 📋 Recent Changes (Last 30 days)

- **2025-11-01**: Qwen Model Unification Update - Updated Comment Groups phase to use Qwen 2.5-72B for complete analytical pipeline consistency (Map, Medium Scoring, Translation, Language Validation, Comment Groups) and removed legacy GPT-4o-mini references
- **2025-11-01**: Documentation Alignment Update - Comprehensive documentation synchronization with current codebase state including: corrected project structure paths, updated migration numbering with duplicate file notes, enhanced backend scripts categorization (25+ drift analysis scripts documented), corrected frontend port information (Vite default 5173), and fixed test file locations
- **2025-10-31**: Qwen Model Configuration Refactor - Implemented unified MODEL_ANALYSIS environment variable for all Qwen services (Map, Medium Scoring, Translation, Language Validation), enabling consistent model architecture with bulletproof rollback mechanism
- **2025-10-29**: Complete Documentation Synchronization - Final comprehensive audit and 100% alignment of documentation with codebase, including structural fixes, API endpoint corrections, backend scripts documentation, and test files coverage
- **2025-10-26**: Docker Deployment VPS Implementation - Complete production-ready deployment infrastructure with automated deployment script, SSL/HTTPS configuration, security hardening, and comprehensive documentation
- **2025-10-25**: Enhanced Progress UI with Real-time Expert Feedback - Added contextual phase descriptions, active expert count display, warning indicators for long-running processes, and frontend-only final_results phase
- **2025-10-25**: Language Validation Phase Implementation - Added eight-phase pipeline with language consistency validation and Russian-to-English translation
- **2025-10-24**: Fixed Post ID Scrolling for Multi-Expert Interface - Standardized DOM ID generation between PostCard and PostsList components using consistent expertId prop
- **2025-10-23**: Medium Posts Hybrid Reranking System - Qwen 2.5-72B scoring with threshold ≥0.7 and top-5 selection
- **2025-10-22**: Channel Username Migration - Added channel_username field to posts table for better channel identification and tracking
- **2025-10-16**: Multi-Expert Sync Optimization v3.0 - Complete workflow integration
- **2025-10-15**: Map Phase Retry Mechanism - 95%+ reliability improvement
- **2025-10-14**: Data Selection Optimization - HIGH only filtering
- **2025-10-12**: Parallel Multi-Expert Processing - All experts processed simultaneously

*For detailed change history, see git log*

## 🎯 Key Architectural Decisions

### Telegram Entity Conversion
- All Telegram entities converted to markdown at import time
- Frontend uses `react-markdown` with `remark-gfm` plugin
- **Critical**: Reimporting data loses drift analysis results

### SSE Parsing Fix
- Frontend SSE parser must process line-by-line
- Each `data: {json}` line is separate event
- Buffer incomplete lines when chunks are split mid-JSON

### Field Naming Convention
- **ALWAYS use `telegram_message_id`** NOT `telegram_id`
- Matches SQLAlchemy Post model implementation

### Multi-Expert Architecture
- All tables have `expert_id` field
- Complete data isolation between experts
- Parallel processing of all experts by default

### Unified Model Configuration
- **Environment-driven**: All Qwen services (Map, Medium Scoring, Translation, Language Validation, Comment Groups) use `MODEL_ANALYSIS` environment variable
- **Bulletproof Rollback**: Single environment variable change instantly switches ALL Qwen services
- **Consistent Management**: Unified configuration eliminates model mismatch risks
- **Service Integration**: All 5 analytical services read model configuration at startup for consistency

### Frontend DOM ID Generation
- **Consistent expertId usage**: PostCard and PostsList components use `expertId` prop for DOM element IDs
- **ID Pattern**: `post-${expertId || 'unknown'}-${telegram_message_id}` for reliable element lookup
- **Backward Compatibility**: Fallback to `post-${telegram_message_id}` for edge cases
- **Post Reference Clicking**: Enables reliable scrolling to posts from expert responses across all experts

### Medium Posts Hybrid Reranking
- **Differential Processing**: HIGH posts go through Resolve phase, selected Medium posts bypass it
- **Hybrid Scoring**: Combines threshold-based (≥0.7) and top-K (top-5) selection strategies
- **Memory Management**: Maximum 50 Medium posts processed to prevent memory issues
- **Security**: API key masking in error logs and input sanitization
- **Multi-Expert Support**: Maintains expert isolation throughout reranking process

### Language Validation Phase
- **Language Consistency**: Validates response language matches query language
- **Translation Capability**: Translates Russian responses to English when mismatch detected
- **Model Integration**: Uses configurable Qwen model via MODEL_ANALYSIS environment variable
- **Error Handling**: Graceful degradation with fallback to original text
- **SSE Progress Tracking**: Real-time validation status updates with expert_id context
- **Multi-Expert Support**: Maintains expert isolation throughout validation process

### Enhanced Progress UI System
- **Real-time Expert Feedback**: Displays active expert count during processing with contextual messages
- **Contextual Phase Descriptions**: User-friendly descriptions for each pipeline phase (Map, Resolve, Reduce, Comments, Final)
- **Warning Indicators**: Visual warnings (orange color, ⚠️ icon) for processes exceeding 300 seconds
- **Frontend-only Phase Management**: Final_results phase exists only in frontend for completion detection
- **Enhanced Phase Status Logic**: Resolve phase combines with medium_scoring events for comprehensive status tracking
- **Multi-Expert Progress Tracking**: Active expert count extracted from SSE events using expert_id
- **Improved User Experience**: Better text layout with proper spacing and colon formatting

*For detailed multi-expert setup see `/docs/multi-expert-guide.md`*

## 🛠️ Testing Strategy

For MVP, use validation through prepared Q&A sets:
- Prepare 5-10 queries with known expected answers
- Focus on completeness (finding all relevant posts)
- Document which posts should be found for each query
- Each query processed fresh (no caching in MVP)

### Multi-Expert Testing
- Verify each expert processes independently
- Check parallel processing reduces total time
- Ensure SSE events contain correct `expert_id`
- Test expert filter parameter


## 📁 Important File Locations

- **Main Pipeline**: `backend/src/services/`
- **Map Service**: `backend/src/services/map_service.py`
- **Reduce Service**: `backend/src/services/reduce_service.py`
- **Language Validation Service**: `backend/src/services/language_validation_service.py`
- **Medium Scoring Service**: `backend/src/services/medium_scoring_service.py`
- **Comment Group Map Service**: `backend/src/services/comment_group_map_service.py`
- **Comment Synthesis Service**: `backend/src/services/comment_synthesis_service.py`
- **Fact Validation Service**: `backend/src/services/fact_validator.py`
- **Log Service**: `backend/src/services/log_service.py`
- **Translation Service**: `backend/src/services/translation_service.py`
- **OpenRouter Adapter**: `backend/src/services/openrouter_adapter.py`
- **Hybrid LLM Adapter**: `backend/src/services/hybrid_llm_adapter.py`
- **Hybrid LLM Monitor**: `backend/src/services/hybrid_llm_monitor.py`
- **Google AI Studio Client**: `backend/src/services/google_ai_studio_client.py`
- **Resolve Service**: `backend/src/services/resolve_service.py`
- **Simple Resolve Service**: `backend/src/services/simple_resolve_service.py`
- **Medium Scoring Prompt**: `backend/prompts/medium_scoring_prompt.txt`
- **API Endpoints**: `backend/src/api/simplified_query_endpoint.py`
- **Database Models**: `backend/src/models/`
- **Utility Functions**: `backend/src/utils/`
- **Entities Converter**: `backend/src/utils/entities_converter.py`
- **Language Utils**: `backend/src/utils/language_utils.py`
- **Prompts**: `backend/prompts/`
- **Frontend Components**: `frontend/src/components/`
- **ProgressSection Component**: `frontend/src/components/ProgressSection.tsx`
- **PostCard Component**: `frontend/src/components/PostCard.tsx`
- **PostsList Component**: `frontend/src/components/PostsList.tsx`
- **Migration Scripts**: `backend/migrations/`
- **Production Deployment**: `fly.toml`, `Dockerfile`
- **Fly.io Configuration**: Automatic SSL/HTTPS and persistent storage
- **Environment Variables**: Set via `fly secrets set`

## Sessions System Behaviors

@CLAUDE.sessions.md