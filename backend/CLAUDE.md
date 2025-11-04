
# Backend Services - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview, Common Tasks)

## 🚀 Backend Service Purpose
FastAPI backend service providing multi-expert query processing with Map-Resolve-Reduce pipeline, real-time SSE streaming, and VPS/cloud deployment support.

## Narrative Summary
The backend implements a sophisticated query processing system that retrieves relevant content from expert Telegram channels and synthesizes comprehensive answers. It features a 7-phase pipeline with hybrid multi-model LLM strategy (Primary → Fallback), language validation, parallel multi-expert processing, Telegram synchronization, and comprehensive drift analysis for comment discussions. The service includes robust error handling with user-friendly messages and is containerized with Docker for VPS/cloud deployment.

## Key Files
- `src/api/main.py` - FastAPI application with CORS, SSE, error handling, and environment configuration
- `src/api/simplified_query_endpoint.py` - Main multi-expert query endpoint with parallel processing and SSE
- `src/services/map_service.py` - Phase 1: Content relevance detection with hybrid model system
- `src/services/medium_scoring_service.py` - Phase 2: Advanced post reranking with scoring
- `src/services/simple_resolve_service.py` - Phase 3: Database link expansion (depth 1)
- `src/services/reduce_service.py` - Phase 4: Answer synthesis with hybrid model system
- `src/services/language_validation_service.py` - Phase 5: Language consistency validation
- `src/services/comment_group_map_service.py` - Phase 6: Comment drift analysis
- `src/services/comment_synthesis_service.py` - Phase 7: Comment insights extraction
- `src/services/translation_service.py` - Post translation support
- `src/utils/error_handler.py` - User-friendly error processing system
- `src/config.py` - Hybrid model configuration management
- `Dockerfile` - Production container configuration for deployment

## API Endpoints
- `GET /health` - Health check with service status validation
- `POST /api/v1/query` - Main multi-expert query endpoint with SSE streaming and parallel processing
- `GET /api/v1/posts/{post_id}` - Retrieve individual post details with comments and translation support
- `POST /api/v1/posts/by-ids` - Batch retrieve multiple posts by IDs
- `POST /api/v1/import` - Import Telegram JSON data with expert assignment
- `POST /api/v1/log-batch` - Debug logging endpoint for frontend development
- `GET /api/info` - API information and feature listing

## Production Deployment Configuration
### Docker Production Architecture
- **Production Dockerfile**: `backend/Dockerfile` with multi-stage build and security hardening
- **Health Check**: `/health` endpoint with 30s intervals, 40s start period
- **Restart Policy**: `unless-stopped` for production stability
- **Resource Limits**: 1GB memory, 0.5 CPU limit, 512MB reservation
- **Security**: Non-root appuser, read-only filesystem where possible

### Production Environment Variables
```bash
# Required: OpenRouter API (primary)
OPENROUTER_API_KEY=sk-or-your-openrouter-api-key-here

# Optional: Google AI Studio API (automatic fallback)
GOOGLE_AI_STUDIO_API_KEY=your-google-ai-studio-api-key-here

# Hybrid Model Configuration
# Map Phase: Primary → Fallback mechanism
MODEL_MAP_PRIMARY=gemini-2.0-flash-lite
MODEL_MAP_FALLBACK=qwen/qwen-2.5-72b-instruct

# Synthesis Phase: Primary → Fallback mechanism
MODEL_SYNTHESIS_PRIMARY=gemini-2.0-flash
MODEL_SYNTHESIS_FALLBACK=qwen/qwen-2.5-72b-instruct

# Analysis Tasks (single model)
MODEL_ANALYSIS=qwen/qwen-2.5-72b-instruct
MODEL_COMMENT_GROUPS=qwen/qwen-2.5-72b-instruct

# Database Configuration
DATABASE_URL=sqlite:///data/experts.db

# Production Domain (must match SSL certificate)
PRODUCTION_ORIGIN=https://your-domain.com

# Production Settings
ENVIRONMENT=production
API_HOST=0.0.0.0
API_PORT=8000
LOG_LEVEL=INFO
PORT=8000

# Performance Settings
MAX_POSTS_LIMIT=500
CHUNK_SIZE=20
REQUEST_TIMEOUT=300

# Optional: Telegram API for synchronization
TELEGRAM_API_ID=your-telegram-api-id
TELEGRAM_API_HASH=your-telegram-api-hash
TELEGRAM_CHANNEL=your-channel-name
```

### Production Docker Configuration
- **Base Image**: Python 3.11-slim with security updates
- **Working Directory**: /app
- **User**: Non-root appuser (UID 1000) for security
- **Health Check**: Built-in Docker health check with curl
- **Port**: 8000 exposed to internal network only
- **Command**: `python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info`
- **Volumes**: `/app/data` for SQLite persistence, `/app/logs` for application logs

### Production Deployment Workflow
```bash
# Quick production deployment (15 minutes)
./deploy.sh                    # Automated deployment with health checks
./deploy.sh status            # Check service status
./deploy.sh logs              # View application logs
./deploy.sh restart           # Restart services
```

### SSL and HTTPS Configuration
- **SSL Termination**: Handled by nginx reverse proxy
- **Security Headers**: HSTS, X-Frame-Options, CSP, etc.
- **Certificate Management**: Automated Let's Encrypt renewal via `update-ssl.sh`
- **HTTPS Only**: All traffic redirected to HTTPS in production

## Integration Points

### Consumes
- **OpenAI/OpenRouter API** - Multi-model LLM processing (Qwen, Gemini, GPT-4o-mini)
- **SQLite Database** - Local and VPS data storage
- **Telegram API** - Channel synchronization and comment fetching

### Provides
- **REST API** - Query processing and data management endpoints
- **SSE Streaming** - Real-time progress updates during query processing
- **Health Endpoint** - Service status and configuration validation

## Local Development Setup

### Prerequisites
- Python 3.11+ with pip package manager
- OpenRouter API key (required) and/or Google AI Studio API key (optional)
- SQLite database (for local development)

### Development Server
```bash
# Install dependencies
pip install -r requirements.txt

# Run development server
cd backend && python3 -m uvicorn src.api.main:app --reload --port 8000

# Health check validation
curl -s http://localhost:8000/health | jq '.'
# Should return API key status and database health
```

### API Testing
```bash
# Query all experts (default)
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "Что такое AI agents?", "stream_progress": false}' \
  -o /tmp/result.json

# Query specific expert
curl -X POST http://localhost:8000/api/v1/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is AI?", "expert_filter": ["refat"], "stream_progress": false}'
```

## Key Architectural Patterns

### Multi-Expert Parallel Processing
- Simultaneous processing of all experts in database
- Expert data isolation at database level
- Parallel async tasks with individual SSE progress tracking
- Dynamic expert detection with optional filtering

### Seven-Phase Pipeline Architecture
1. **Map Phase** - Content relevance detection with hybrid model system (Primary → Fallback)
2. **Medium Scoring Phase** - Advanced post reranking with score ≥ 0.7 filtering (max 5 posts)
3. **Resolve Phase** - Database link expansion for HIGH posts only (depth 1)
4. **Reduce Phase** - Answer synthesis with hybrid model system
5. **Language Validation Phase** - Language consistency validation and translation
6. **Comment Groups Phase** - Drift analysis for relevant discussions
7. **Comment Synthesis Phase** - Complementary insights extraction

### Hybrid Multi-Model Strategy
- **Map Phase**: Gemini 2.0 Flash Lite → Qwen 2.5-72B (Primary → Fallback)
- **Analysis Tasks**: Qwen 2.5-72B (medium scoring, translation, validation)
- **Synthesis Phase**: Gemini 2.0 Flash → Qwen 2.5-72B (Primary → Fallback)
- **Comment Groups**: Qwen 2.5-72B (drift analysis)
- **Google AI Studio Integration**: Free tier usage with automatic OpenRouter fallback

### Retry Mechanism (Map Phase)
- Two-layer retry strategy: 3 per-chunk + 1 global retry attempts
- Exponential backoff with comprehensive error handling
- Recovers from HTTP errors, JSON decode errors, and validation failures
- 95%+ recovery rate for failed chunks

## Configuration Management

### Environment Variables Priority
1. Production environment variables (VPS/cloud)
2. .env file (local development)
3. Default values in code

### Database Configuration
- **Local**: SQLite (`data/experts.db` - located in `backend/data/` directory, 56MB)
- **Production**: SQLite (`/app/data/experts.db` on production servers)
- **Async Support**: SQLAlchemy 2.0 with aiosqlite driver
- **Migrations**: 8 migration scripts in `backend/migrations/` directory

### Hybrid Model Configuration
- Primary models via Google AI Studio API (free tier)
- Fallback models via OpenRouter API (paid)
- Automatic model switching on quota/rate-limit errors
- All prompts externalized to `prompts/` directory
- Configurable chunk sizes and processing parameters via environment variables

## Production Deployment Notes

### Production Architecture Overview
- **3-Service Setup**: nginx-reverse-proxy → backend-api → frontend-app
- **Internal Network**: Custom Docker network (172.20.0.0/16) for secure communication
- **SSL Termination**: nginx handles HTTPS, backend receives HTTP internally
- **Resource Isolation**: Memory and CPU limits per service

### Database Management
- **Persistence**: SQLite database mounted at `/app/data/experts.db`
- **Backup Strategy**: Manual backup via `sqlite3 .backup` or file copy
- **Migration**: Upload development database to production VPS
- **Permissions**: Database file owned by appuser (UID 1000)

### Security Hardening
- **Non-root Container**: Backend runs as appuser (UID 1000)
- **Network Isolation**: Only accessible via nginx reverse proxy
- **Environment Variables**: Sensitive data passed via Docker environment
- **Health Monitoring**: Built-in health checks with automatic restarts
- **CORS Configuration**: Locked to production domain only

### Performance and Monitoring
- **Resource Limits**: 1GB memory, 0.5 CPU limit for stability
- **Health Checks**: 30s intervals, 40s start period, 3 retries
- **Logging**: Structured JSON logs to `/app/logs` directory
- **Restart Policy**: `unless-stopped` for high availability
- **Graceful Shutdown**: 10s timeout for SIGTERM handling

### VPS Security Integration
- **Firewall**: UFW configured to allow only HTTPS (443) and HTTP (80)
- **Intrusion Prevention**: fail2ban for SSH and web protection
- **SSL Certificates**: Automated Let's Encrypt renewal
- **SSH Hardening**: Key-based authentication only, root login disabled
- **System Updates**: Automatic security patch management

### Production Troubleshooting
```bash
# Check service health
curl https://your-domain.com/health

# View backend logs
./deploy.sh logs | grep backend-api

# Debug database connectivity
docker-compose exec backend-api sqlite3 data/experts.db ".tables"

# Monitor resource usage
docker stats experts-panel-backend

# Check SSL certificates
./update-ssl.sh status
```

## Error Handling System

### Purpose
User-friendly error processing system that converts technical errors into actionable messages for users while maintaining detailed logging for developers.

### Key Components
- `utils/error_handler.py` - Central error processing with user-friendly messages
- Integration with SSE streaming for real-time error reporting
- Context-aware error suggestions and recovery actions
- Support for API key errors, rate limits, and service failures

### Error Categories
- **API Key Errors**: Configuration issues and authentication failures
- **Rate Limit Errors**: Quota exceeded and service throttling
- **Network Errors**: Connection timeouts and service unavailability
- **Validation Errors**: Invalid input and malformed requests
- **System Errors**: Database issues and internal failures

## Language Enforcement System

### Purpose
Multi-lingual support system that detects query language and enforces consistent response language across all LLM calls.

### Key Components
- `utils/language_utils.py:10-60` - Language detection engine
- `utils/language_utils.py:62-104` - Language instruction generation
- `utils/language_utils.py:107-172` - Prompt preparation utilities

### Integration Points
The language system is integrated into all core LLM services:
- **Map Service** (`services/map_service.py:18`) - Uses `prepare_system_message_with_language()` for language enforcement
- **Reduce Service** (`services/reduce_service.py:15`) - Uses `prepare_system_message_with_language()`
- **Comment Group Map Service** (`services/comment_group_map_service.py:22`) - Uses `prepare_prompt_with_language_instruction()`
- **Comment Synthesis Service** (`services/comment_synthesis_service.py:13`) - Uses both system message and prompt preparation functions

### Language Detection Logic
- Analyzes character patterns (ASCII vs Cyrillic)
- Counts words for more accurate detection
- Defaults to Russian for ambiguous cases
- Enforces response language regardless of source content language

### Usage Pattern
```python
from ..utils.language_utils import prepare_prompt_with_language_instruction, prepare_system_message_with_language

# Method 1: System message override (preferred for LLMs)
system_message = prepare_system_message_with_language(base_system, query)

# Method 2: Prompt prepending (fallback method)
enhanced_prompt = prepare_prompt_with_language_instruction(prompt_template, query)
```

## Related Documentation
- `DEPLOYMENT.md` - Complete production deployment guide
- `QUICK_START.md` - 15-minute VPS deployment quick start
- `frontend/CLAUDE.md` - Frontend architecture and API integration
- `prompts/README.md` - LLM prompt documentation
- `migrations/` - Database migration scripts
- `../CLAUDE.md` - Overall project architecture and commands
- `security/README.md` - VPS security hardening guide
- `nginx/nginx-prod.conf` - Production SSL and reverse proxy configuration

## Troubleshooting Common Issues

### Development Environment
- **Environment variables not loading**: Ensure `load_dotenv()` is called in `main.py`
- **Port conflicts**: Use `--port 8000` for backend, frontend uses 3000
- **Database issues**: SQLite for both local and production

### Production Deployment
- **Build failures**: Check Dockerfile paths and requirements.txt
- **Health check failures**: Verify `/health` endpoint responds correctly
- **Environment variables**: Set all required variables in hosting environment

### API Issues
- **CORS errors**: Check CORS origins configuration
- **OpenAI API failures**: Validate API key format and permissions
- **SSE streaming issues**: Ensure client supports Server-Sent Events

