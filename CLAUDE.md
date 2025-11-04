@sessions/CLAUDE.sessions.md

# Experts Panel - Multi-Expert Query Processing System

Sophisticated 7-phase pipeline system for analyzing expert Telegram channels and synthesizing comprehensive answers using multiple AI models.

## 🚀 Quick Start (5 minutes)

### Prerequisites
- Python 3.11+ and Node.js 18+
- OpenRouter API key
- Git clone of repository

### 1. Environment Setup
```bash
# Create .env file in project root
echo "OPENROUTER_API_KEY=your-key-here" > .env

# Backend dependencies
cd backend && pip install -r requirements.txt

# Frontend dependencies
cd ../frontend && npm install
```

### 2. Start Development Servers
```bash
# Terminal 1: Backend (port 8000)
cd backend && python3 -m uvicorn src.api.main:app --reload --port 8000

# Terminal 2: Frontend (port 3000)
cd frontend && npm run dev
```

### 3. Verify Installation
- Backend: http://localhost:8000/health
- Frontend: http://localhost:3000
- Test query: "What are the latest AI trends?"

### 4. First Query
```bash
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Your question", "stream_progress": false}'
```

## 🏗️ Architecture Overview

### 7-Phase Processing Pipeline
1. **Map Phase** - Content relevance detection with hybrid model system (Primary → Fallback)
2. **Medium Scoring** - Advanced post ranking with configurable analysis model
3. **Resolve Phase** - Database link expansion (depth 1 only)
4. **Reduce Phase** - Answer synthesis with hybrid model system
5. **Language Validation** - Response language consistency validation
6. **Comment Groups** - Discussion drift analysis
7. **Comment Synthesis** - Complementary insights extraction

### Multi-Model Strategy (Hybrid System)
- **Map Phase**: Primary → Fallback mechanism (Gemini 2.0 Flash Lite → Qwen 2.5-72B)
- **Analysis**: Qwen 2.5-72B (medium scoring, translation, validation)
- **Synthesis**: Primary → Fallback mechanism (Gemini 2.0 Flash → Qwen 2.5-72B)
- **Comment Groups**: Qwen 2.5-72B (drift analysis)

### Multi-Expert Architecture
- Complete data isolation between experts
- Parallel processing of all experts
- Real-time progress tracking with SSE streaming

## 📁 Component Documentation

### Backend Services & API
**📖 See: `backend/CLAUDE.md`**

Complete FastAPI backend with:
- Multi-expert query processing pipeline with parallel processing
- 9 specialized services for different phases
- Real-time SSE streaming for progress tracking with error handling
- Hybrid multi-model LLM integration (OpenRouter + Google AI Studio)
- SQLite database with 8 migration scripts (56MB active database)
- Production-ready Docker deployment

**Key Files:**
- `src/api/simplified_query_endpoint.py` - Main multi-expert query processing
- `src/services/map_service.py` - Content relevance detection with hybrid models
- `src/services/medium_scoring_service.py` - Advanced post reranking
- `src/services/language_validation_service.py` - Language consistency validation
- `src/config.py` - Hybrid model configuration management

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
**Location:** `backend/data/experts.db` (56MB active database)

- **Posts**: Expert channel content with metadata and expert isolation
- **Comments**: Hierarchical comment structure with expert associations
- **Links**: Post relationships and connections (depth 1 only)
- **Expert Isolation**: Complete data separation by expert_id
- **Migration Scripts**: 8 database evolution scripts in `backend/migrations/`

## 🔧 Common Development Tasks

### Adding New Expert
```bash
# Import Telegram data
cd backend && python -m src.data.json_parser export.json --expert-id new_expert

# Verify import
python -m src.models.database
# > list experts
```

### Database Operations
```bash
cd backend

# Interactive database management
python -m src.models.database

# Database backup
sqlite3 data/experts.db ".backup data/backup.db"

# Run migrations
sqlite3 data/experts.db < migrations/008_fix_comment_unique_constraint.sql
```

### Model Configuration
```bash
# Hybrid Model System (Primary → Fallback)
# Map Phase: Try Google AI Studio first, fallback to OpenRouter
MODEL_MAP_PRIMARY=gemini-2.0-flash-lite
MODEL_MAP_FALLBACK=qwen/qwen-2.5-72b-instruct

# Synthesis Phase: Try Google AI Studio first, fallback to OpenRouter
MODEL_SYNTHESIS_PRIMARY=gemini-2.0-flash
MODEL_SYNTHESIS_FALLBACK=qwen/qwen-2.5-72b-instruct

# Analysis Tasks (single model)
MODEL_ANALYSIS=qwen/qwen-2.5-72b-instruct
MODEL_COMMENT_GROUPS=qwen/qwen-2.5-72b-instruct

# Google AI Studio API Keys (comma-separated for rotation)
GOOGLE_AI_STUDIO_API_KEY=your-google-ai-studio-key-here

# See backend/CLAUDE.md and .env.example for complete configuration
```

### Testing Pipeline
```bash
# Test all experts
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Test query", "stream_progress": false}'

# Test specific expert
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Test query", "expert_filter": ["refat"]}'

# Test debug logging endpoint
curl -X POST http://localhost:8000/api/v1/log-batch \
  -H "Content-Type: application/json" \
  -d '[{"timestamp": "2025-01-02T10:00:00Z", "type": "console", "source": "test", "message": "Test log entry"}]'

# Test individual post retrieval with translation
curl "http://localhost:8000/api/v1/posts/12345?expert_id=refat&query=What is AI?&translate=true"
```

## 🚀 Production Deployment

### Quick Fly.io Deployment (15 minutes)
```bash
# Install Fly CLI
curl -L https://fly.io/install.sh | sh && fly auth login

# Deploy application
fly deploy

# Configure secrets
fly secrets set OPENROUTER_API_KEY=your-key-here

# Verify deployment
fly open && curl https://your-app.fly.dev/health
```

**Complete deployment guide:** See `backend/CLAUDE.md` → "Production Deployment"

## 🔍 Troubleshooting

### Server Issues
```bash
# Check backend health
curl -s http://localhost:8000/health | jq '.'

# Check frontend availability
curl -s http://localhost:3000 > /dev/null && echo "Frontend OK"

# View logs
tail -f backend/backend.log      # Backend API and pipeline logs
tail -f frontend/frontend.log    # Frontend debug logs
```

### Common Problems
- **Port conflicts**: Backend uses 8000, Frontend uses 3000
- **Environment variables**: Ensure .env file with OPENROUTER_API_KEY
- **Database location**: Active DB is in `backend/data/experts.db`

### Debug Commands
```bash
# Monitor expert processing
grep "expert_id" backend/backend.log | tail -10

# Track pipeline phases
grep "phase.*complete" backend/backend.log | tail -5

# Frontend event monitoring
grep "api.*query" frontend/frontend.log | tail -5
```

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
**Last Updated:** 2025-11-04
**Architecture:** Multi-expert, hybrid multi-model LLM pipeline with real-time progress tracking
**Key Features:** Parallel expert processing, hybrid model fallback system, language validation, comment synthesis, user-friendly error handling