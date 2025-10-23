# Experts Panel Development Guidelines

Auto-generated from feature plans. Last updated: 2025-10-23

## Active Technologies
- Python 3.11+ with FastAPI and Pydantic v2
- SQLite with SQLAlchemy 2.0
- React 18 with TypeScript
- OpenRouter API - Multi-model strategy:
  - Qwen 2.5-72B Instruct for Map phase
  - Gemini 2.0 Flash for Reduce and Comment Synthesis
  - GPT-4o-mini for Comment Groups matching
- Docker for deployment
- VPS/Cloud hosting ready

## Project Structure
```
backend/
├── src/
│   ├── models/       # SQLAlchemy models
│   ├── services/     # Map-Resolve-Reduce pipeline
│   ├── api/          # FastAPI endpoints
│   └── data/         # Import and parsing
├── prompts/          # LLM prompts (optimized per model)
├── migrations/       # Database migrations
└── tests/            # Validation queries

frontend/
├── src/
│   ├── components/   # React components
│   ├── services/     # API client with SSE streaming
│   └── types/        # TypeScript interfaces
└── public/           # Static assets

data/
├── exports/          # Telegram JSON files
└── experts.db        # SQLite database
```

## 🗺️ Key Documentation References

### Core Architecture
- **Pipeline Architecture**: `/docs/pipeline-architecture.md` 🚀
- **Multi-Expert Setup**: `/docs/multi-expert-guide.md` 👥

### Quick Reference
- **Database Operations**: See `models/database.py`
- **API Endpoints**: See `api/simplified_query_endpoint.py`
- **Import Scripts**: See `data/json_parser.py`

## Commands

### Backend Development
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (ONLY way that works!)
cd backend && uv run uvicorn src.api.main:app --reload --port 8000

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
# Create database
sqlite3 data/experts.db < schema.sql

# Run migrations (apply in order)
sqlite3 data/experts.db < backend/migrations/001_create_comment_group_drift.sql
sqlite3 data/experts.db < backend/migrations/002_add_sync_state.sql
sqlite3 data/experts.db < backend/migrations/003_add_expert_id.sql
sqlite3 data/experts.db < backend/migrations/004_add_expert_id_to_drift.sql
sqlite3 data/experts.db < backend/migrations/006_add_unique_telegram_message_id.sql

# Backup database
sqlite3 data/experts.db ".backup data/backup.db"

# Query drift groups
sqlite3 data/experts.db "SELECT post_id, has_drift, analyzed_at FROM comment_group_drift WHERE has_drift=1;"
```

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

The system uses a **six-phase pipeline**:

1. **Map Phase** - Qwen 2.5-72B finds relevant posts
2. **Filter Phase** - Keeps only HIGH relevance posts
3. **Resolve Phase** - Expands context via database links
4. **Reduce Phase** - Gemini 2.0 Flash synthesizes answer
5. **Comment Groups** - Finds relevant comment discussions
6. **Comment Synthesis** - Extracts complementary insights

*For detailed pipeline architecture see `/docs/pipeline-architecture.md`*

## 🚨 Critical Backend Startup

### ONLY Working Method:
1. Ensure `backend/src/api/main.py` contains:
   ```python
   from dotenv import load_dotenv
   load_dotenv()
   ```

2. Run ONLY this way:
   ```bash
   cd backend && uv run uvicorn src.api.main:app --reload --port 8000
   ```

### DOES NOT WORK:
- ❌ source .env && uv run...
- ❌ export $(cat .env) && uv run...
- ❌ uv run --env-file .env...

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
- **API Endpoints**: `backend/src/api/simplified_query_endpoint.py`
- **Database Models**: `backend/src/models/`
- **Prompts**: `backend/prompts/`
- **Frontend Components**: `frontend/src/components/`
- **Migration Scripts**: `backend/migrations/`

## Sessions System Behaviors

@CLAUDE.sessions.md