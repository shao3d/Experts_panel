
# Backend Services - Experts Panel

**📖 See main documentation:** `../CLAUDE.md` (Quick Start, Architecture Overview, Common Tasks)

## 🚀 Backend Service Purpose
FastAPI backend service providing multi-expert query processing with Map-Resolve-Reduce pipeline, real-time SSE streaming, and VPS/cloud deployment support.

## Narrative Summary
The backend implements a sophisticated query processing system that retrieves relevant content from expert Telegram channels and synthesizes comprehensive answers. It features an 8-phase pipeline with Gemini-only LLM strategy (single API key with auto-retry), language validation, parallel multi-expert processing, Telegram synchronization, and comprehensive drift analysis for comment discussions. The service includes robust error handling with user-friendly messages and is containerized with Docker for VPS/cloud deployment.

## Key Files
- `src/api/main.py` - FastAPI application with CORS, SSE, error handling, admin auth, and production configuration
- `src/api/simplified_query_endpoint.py` - Main multi-expert query endpoint with parallel processing and enhanced SSE
- `src/api/admin_endpoints.py` - Admin authentication and production configuration endpoints
- `src/services/map_service.py` - Phase 1: Content relevance detection with Gemini
- `src/services/medium_scoring_service.py` - Phase 2: Advanced post reranking with Gemini
- `src/services/simple_resolve_service.py` - Phase 3: Database link expansion (depth 1)
- `src/services/reduce_service.py` - Phase 4: Answer synthesis with Gemini
- `src/services/language_validation_service.py` - Phase 5: Language consistency validation
- `src/services/comment_group_map_service.py` - Phase 6: Comment drift analysis + main source author clarifications
- `src/services/comment_synthesis_service.py` - Phase 7: Comment insights extraction with priority for main source clarifications
- `src/services/drift_scheduler_service.py` - Offline Drift Analysis with **gemini-3-flash-preview** via unified client
- `src/services/translation_service.py` - Translation service with Gemini
- `src/utils/error_handler.py` - Enhanced user-friendly error processing system
- `src/config.py` - Gemini-only model configuration management
- `src/services/google_ai_studio_client.py` - Google AI Studio API client (single-key with auto-retry)
- `src/services/monitored_client.py` - LLM call monitoring wrapper
- `src/services/llm_monitor.py` - LLM statistics and health tracking
- `fly.toml` - Fly.io production deployment configuration

## API Endpoints
- `GET /health` - Health check with service status validation
- `GET /api/v1/experts` - Dynamic expert loading from database with metadata
- `POST /api/v1/query` - Main multi-expert query endpoint with enhanced SSE streaming and parallel processing
- `GET /api/v1/posts/{post_id}` - Retrieve individual post details with comments and translation support
- `POST /api/v1/import` - Import Telegram JSON data with expert assignment
- `POST /api/v1/log-batch` - Enhanced debug logging endpoint for frontend development
- `GET /api/info` - API information and feature listing
- **Admin Endpoints** (protected):
  - `GET /api/v1/admin/config` - Get production configuration
  - `POST /api/v1/admin/config` - Update production settings
  - `GET /api/v1/admin/status` - System status and metrics

## Production Deployment Configuration
### Docker Production Architecture
- **Production Dockerfile**: `backend/Dockerfile` with multi-stage build and security hardening
- **Health Check**: `/health` endpoint with 30s intervals, 40s start period
- **Restart Policy**: `unless-stopped` for production stability
- **Resource Limits**: 1GB memory, 0.5 CPU limit, 512MB reservation
- **Security**: Non-root appuser, read-only filesystem where possible

A complete list of required and optional environment variables for production is available in the `.env.example` file. For production, ensure `ENVIRONMENT` is set to `production` and all necessary API keys and secrets are provided.

### Production Docker Configuration
- **Base Image**: Python 3.11-slim with security updates
- **Working Directory**: /app
- **User**: Non-root appuser (UID 1000) for security
- **Health Check**: Built-in Docker health check with curl
- **Port**: 8000 exposed to internal network only
- **Command**: `python -m uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info`
- **Volumes**: `/app/data` for SQLite persistence, `/app/logs` for application logs

The project can be deployed to Fly.io using the `fly.toml` configuration file and the `flyctl` CLI. Alternatively, a custom deployment script, `deploy.sh`, is provided in the root directory for automated Docker-based deployments. Refer to these files and the official Fly.io documentation for detailed procedures.

### SSL and HTTPS Configuration
- **SSL Termination**: Handled by nginx reverse proxy
- **Security Headers**: HSTS, X-Frame-Options, CSP, etc.
- **Certificate Management**: Automated Let's Encrypt renewal via `update-ssl.sh`
- **HTTPS Only**: All traffic redirected to HTTPS in production

## Integration Points

### Consumes
- **Google AI Studio API** - Gemini models for all LLM processing (single-key with auto-retry)
- **SQLite Database** - Local and VPS data storage
- **Telegram API** - Channel synchronization and comment fetching

### Provides
- **REST API** - Query processing and data management endpoints
- **SSE Streaming** - Real-time progress updates during query processing
- **Health Endpoint** - Service status and configuration validation

## Local Development Setup

### Prerequisites
- Python 3.11+ with pip package manager
- Google AI Studio API key(s) — get from https://aistudio.google.com/app/apikey
- SQLite database (for local development)

### Development Server
To set up the development environment, install the dependencies listed in `backend/requirements.txt`. The `quickstart.sh` script in the project root can automate this process.

To run the development server, you can use the `uvicorn` command as detailed in the `quickstart.sh` script's output.

### API Testing
Once the server is running, you can test the API. For simple health checks, access the `/health` endpoint. For sending queries and exploring all endpoints, use the interactive OpenAPI documentation available at `/api/docs`.

### Database Maintenance
To keep the database optimized and remove old data (e.g., posts older than 2025), use the pruning script. This script respects foreign key constraints and automatically removes associated comments and links.
```bash
# From project root
python backend/scripts/prune_old_posts.py
```
**Note:** Always create a backup before running destructive maintenance operations.

## Key Architectural Patterns

### Multi-Expert Parallel Processing
- Simultaneous processing of all experts in database
- Expert data isolation at database level
- Parallel async tasks with individual SSE progress tracking
- Dynamic expert detection with optional filtering

### Eight-Phase Pipeline Architecture
1. **Map Phase** - Content relevance detection with Gemini
2. **Medium Scoring Phase** - Advanced post reranking with score ≥ 0.7 filtering (max 5 posts)
3. **Resolve Phase** - Database link expansion for HIGH posts only (depth 1)
4. **Reduce Phase** - Answer synthesis with Gemini
5. **Language Validation Phase** - Language consistency validation and translation
6. **Comment Groups Phase** - Drift analysis for relevant discussions
7. **Comment Synthesis Phase** - Complementary insights extraction

### Gemini-Only Model Strategy
The system uses Google AI Studio with automatic retry on rate limit errors (65s wait). For a detailed breakdown of the models used in each pipeline phase, see the **[Pipeline Architecture Guide](../docs/pipeline-architecture.md)**.

**Current Production Models** (configured via `.env`):
- **Map Phase**: `gemini-2.5-flash-lite` - Lightweight, ultra-fast relevance detection
- **Synthesis (Reduce/Comments)**: `gemini-3-flash-preview` - Pro-grade reasoning for synthesis
- **Analysis (Translation/Validation)**: `gemini-2.0-flash` - Fast, reliable for analysis tasks
- **Medium Scoring**: `gemini-2.0-flash` - Content scoring and ranking
- **Comment Groups**: `gemini-2.0-flash` - Comment relevance detection
- **Drift Analysis** (offline): `gemini-3-flash-preview` - Advanced reasoning for topic drift

**Unified Client Architecture**:
- All services use `google_ai_studio_client.py` for consistent API access
- OpenAI-compatible response format with automatic retry logic
- 65-second wait on rate limit (429) errors with 2 retry attempts
- Centralized error handling and monitoring

**Note**: Model `gemini-3-flash-preview` (released 2026-01-17) is used for synthesis and drift analysis for enhanced reasoning capabilities while maintaining cost efficiency.

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
- **Local**: SQLite (`data/experts.db` - located in `backend/data/` directory, 18MB)
- **Production**: SQLite (`/app/data/experts.db` on production servers)
- **Async Support**: SQLAlchemy 2.0 with aiosqlite driver
- **Migrations**: 10+ migration scripts in `backend/migrations/` directory
- **Expert Metadata**: Centralized expert information with display names and channels
- **Drift Analysis**: Comprehensive comment drift tracking and topic analysis

### Gemini Model Configuration
- All models via Google AI Studio API (Tier 1 paid account)
- Automatic retry on rate limit errors with 65-second wait
- All prompts externalized to `prompts/` directory
- Configurable chunk sizes and processing parameters via environment variables

## Production Deployment Notes

### Production Architecture Overview
- **Fly.io Deployment**: Single-container architecture with persistent volume storage
- **Alternative VPS**: 3-Service Setup (nginx-reverse-proxy → backend-api → frontend-app)
- **Internal Network**: Custom Docker network (172.20.0.0/16) for secure communication
- **SSL Termination**: Automatic HTTPS via Fly.io or nginx reverse proxy
- **Resource Isolation**: Memory and CPU limits per service (1GB memory, 1 CPU for Fly.io)
- **Admin Authentication**: Secure admin endpoints with production configuration management

### Database Management
- **Persistence**: SQLite database mounted at `/app/data/experts.db`
- **Update Strategy**: Automated via `scripts/update_production_db.sh` (Sync -> Drift Analysis -> Compress -> Upload -> Restart)
- **Backup Strategy**: Automated local backup before sync + remote backup on server
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
To troubleshoot a production deployment, first check the service health via its public URL at the `/health` endpoint. For detailed logs, use the `fly logs` command (for Fly.io) or the `deploy.sh` script if applicable. You can also connect to the running container to inspect the database directly. Monitor resource usage via your hosting provider's dashboard (e.g., `docker stats` or Fly.io's metrics).

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
The usage pattern, involving `prepare_system_message_with_language` and `prepare_prompt_with_language_instruction`, can be seen in practice in the various service files, such as `services/map_service.py` and `services/reduce_service.py`.

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
- **Google AI Studio failures**: Validate API key format and check rate limits
- **SSE streaming issues**: Ensure client supports Server-Sent Events

