---
name: docker-deployment-vps
branch: feature/docker-deployment-vps
status: pending
created: 2025-01-25
submodules: []
---

# Implement Docker Deployment for Experts Panel to VPS

## Problem/Goal
Implement complete Docker containerization and deployment strategy for Experts Panel application to Virtual Private Server (VPS) with production-ready configuration, SSL/HTTPS setup, database persistence, and automated deployment workflows.

## Success Criteria
- [ ] Production-ready Docker containers for backend (FastAPI) and frontend (React/Nginx)
- [ ] Docker Compose configuration with proper networking and volume management
- [ ] SSL/HTTPS setup with Let's Encrypt certificates and Nginx reverse proxy
- [ ] Database persistence strategy with Docker volume for SQLite
- [ ] Environment variable management for production
- [ ] Health checks and monitoring configuration
- [ ] Simple deployment script for initial VPS setup
- [ ] Production security hardening and best practices

## Context Manifest

### How Experts Panel Currently Works: Production Architecture Analysis

The Experts Panel is a sophisticated multi-expert query processing system with an eight-phase Map-Resolve-Reduce pipeline that processes user queries against expert Telegram channel content and synthesizes comprehensive answers using multiple LLM models.

**Backend Service Architecture (FastAPI):**
The backend follows a well-structured service-oriented architecture:

**Entry Point & Core Infrastructure:**
- **Main Application**: `/Users/andreysazonov/Documents/Projects/Experts_panel/backend/src/api/main.py` - FastAPI application with comprehensive CORS middleware, request ID tracking, exception handlers, and health check endpoints
- **Health Check Implementation**: Built-in health endpoint at `/health` that validates database connectivity and API key configuration, returning JSON status with `database`, `openai_configured`, and overall `status` fields
- **CORS Configuration**: Dynamic origin handling with development origins (localhost:3000, 3001, 5173, 127.0.0.1 variants) plus production origin via `PRODUCTION_ORIGIN` environment variable
- **Database Initialization**: Automatic table creation via SQLAlchemy Base metadata on startup

**Eight-Phase Processing Pipeline (`backend/src/services/`):**
1. **Map Phase** (`map_service.py`) - Semantic document relevance detection using Qwen 2.5-72B via OpenRouter API, implements robust chunked processing with two-layer retry mechanism (3 per-chunk + 1 global retry)
2. **Medium Scoring Phase** (`medium_scoring_service.py`) - Hybrid reranking system with threshold ≥0.7 and top-5 selection, processes up to 50 Medium posts to prevent memory issues
3. **Differential Resolve Phase** (`simple_resolve_service.py`) - Database link expansion for HIGH relevance posts only (depth 1), selected Medium posts bypass this phase
4. **Reduce Phase** (`reduce_service.py`) - Answer synthesis using Gemini 2.0 Flash with personal style support and comprehensive context integration
5. **Language Validation Phase** (`language_validation_service.py`) - Language consistency validation using Qwen 2.5-72B, translates Russian responses to English when mismatch detected
6. **Comment Groups Phase** (`comment_group_map_service.py`) - Pre-analyzed drift discussion matching using GPT-4o-mini
7. **Comment Synthesis Phase** (`comment_synthesis_service.py`) - Complementary insights extraction using Gemini 2.0 Flash
8. **Response Building** - Multi-expert response assembly with proper attribution and source linking

**Frontend Application (React/TypeScript + Vite):**
- **Build System**: Vite with TypeScript strict mode, React 18 function components with hooks, inline styling for MVP simplicity
- **Production Architecture**: Multi-stage Docker build (Node.js build stage + Nginx production stage) serving static files with gzip compression
- **Key Features**: Real-time SSE streaming for progress updates, enhanced progress UI with active expert count display and contextual phase descriptions, post reference clicking system with consistent DOM ID generation
- **API Integration**: Singleton APIClient with fixed SSE parsing logic, proper error handling, and support for both development and production base URLs

**Database Architecture & Migration System:**
- **Database Engine**: SQLite with SQLAlchemy 2.0 async support (`aiosqlite` driver)
- **Connection Pattern**: `sqlite:///data/experts.db` for sync operations, `sqlite+aiosqlite:///data/experts.db` for async operations
- **Multi-Expert Data Model**: Complete data isolation via `expert_id` fields across all tables, enabling parallel processing of multiple experts
- **Critical Table Structure**:
  - `posts` - Core content with `telegram_message_id`, `expert_id`, channel information
  - `links` - Post-to-post relationships with `source_post_id`, `target_post_id`
  - `comments` - Expert comments with foreign key relationships
  - `comment_group_drift` - Pre-analyzed discussion topics with drift detection results

**Multi-Model LLM Strategy via OpenRouter:**
- **API Integration**: OpenRouter adapter (`backend/src/services/openrouter_adapter.py`) that converts OpenAI SDK to work with OpenRouter API endpoints
- **Model Allocation**:
  - Qwen 2.5-72B Instruct: Map phase, Medium Scoring, Language Validation
  - Gemini 2.0 Flash: Reduce phase, Comment Synthesis
  - GPT-4o-mini: Comment Groups matching
- **API Key Pattern**: System uses `OPENAI_API_KEY` environment variable (not `OPENROUTER_API_KEY`) but routes through OpenRouter API endpoints

### Current Production-Ready Docker Configuration

**Existing Docker Infrastructure Analysis:**

**Backend Container (`/Users/andreysazonov/Documents/Projects/Experts_panel/backend/Dockerfile`):**
```dockerfile
# Production-optimized Python 3.11-slim base image
FROM python:3.11-slim
# Security: Non-root user creation (appuser) with proper directory ownership
# Health check: Integrated curl-based health check every 30s
# Volume strategy: /app/data directory for SQLite persistence
# Exposed port: 8000 with proper uvicorn production configuration
# Environment: Production-ready with proper Python path and buffering settings
```

**Frontend Container (`/Users/andreysazonov/Documents/Projects/Experts_panel/frontend/Dockerfile`):**
```dockerfile
# Multi-stage build optimization
FROM node:18-alpine AS builder  # Build stage with npm ci and build
FROM nginx:alpine AS production  # Lightweight production serving
# Features: Static asset gzip compression, SPA routing support
# Configuration: Custom nginx.conf with API proxy to backend service
```

**Development Docker Compose (`/Users/andreysazonov/Documents/Projects/Experts_panel/docker-compose.yml`):**
```yaml
# Two-service architecture with proper orchestration
services:
  backend:  # Port 8000, health checks, volume mounts, restart policies
  frontend: # Port 3000:80, depends_on backend health, API proxy configuration
# Network isolation: experts-panel-network bridge network
# Volume persistence: ./data:/app/data for SQLite database
# Environment: Production-ready settings with proper variable injection
```

**Current Nginx Configuration (`/Users/andreysazonov/Documents/Projects/Experts_panel/frontend/nginx.conf`):**
```nginx
# Production-ready configuration with:
server {
    listen 80;
    # Gzip compression for text-based assets
    # SPA routing with try_files fallback to index.html
    # API proxy to backend:8000 with proper headers
    # SSE support with proxy_buffering off
    # Static asset caching (1y expiry for JS/CSS/images)
    # Health endpoint proxy for backend health checks
}
```

### Environment Variables & API Configuration Analysis

**Critical Environment Variables for Production:**
```bash
# Primary API Configuration (CRITICAL - uses OPENAI_API_KEY name for OpenRouter)
OPENAI_API_KEY=sk-your-openrouter-api-key-here  # Required for all LLM operations
DATABASE_URL=sqlite:///data/experts.db          # SQLite database path

# Production Domain Configuration
PRODUCTION_ORIGIN=https://your-domain.com       # Dynamic CORS origin addition
API_HOST=0.0.0.0                               # Bind to all interfaces
API_PORT=8000                                   # Backend service port
ENVIRONMENT=production                          # Production mode flag
LOG_LEVEL=INFO                                  # Production logging level

# Pipeline Configuration
MAX_POSTS_LIMIT=500                             # Maximum posts to process
CHUNK_SIZE=20                                   # Processing chunk size
REQUEST_TIMEOUT=300                             # Request timeout in seconds
```

**API Integration Pattern:**
The system uses a sophisticated adapter pattern that converts OpenAI SDK calls to OpenRouter API endpoints:
- **Environment Variable**: Uses `OPENAI_API_KEY` (not `OPENROUTER_API_KEY`) as discovered in code analysis
- **Base URL**: Routes to `https://openrouter.ai/api/v1` instead of OpenAI
- **Model Mapping**: Converts model names (e.g., "gpt-4o-mini" → "openai/gpt-4o-mini")
- **Health Check Integration**: Health endpoint validates `openai_configured = bool(os.getenv("OPENAI_API_KEY"))`

**CORS Configuration Implementation:**
```python
# From backend/src/api/main.py lines 66-89
origins = [
    "http://localhost:3000", "http://localhost:3001", "http://localhost:3002",
    "http://localhost:5173", "http://127.0.0.1:3000", "http://127.0.0.1:3001",
    "http://127.0.0.1:3002", "http://127.0.0.1:5173",
]
production_origin = os.getenv("PRODUCTION_ORIGIN")
if production_origin:
    origins.append(production_origin)
```

### Database Migration & File Structure Analysis

**Confirmed Migration Files (`/Users/andreysazonov/Documents/Projects/Experts_panel/backend/migrations/`):**
```
001_create_comment_group_drift.sql    # Initial drift analysis table
002_add_sync_state.sql                # Telegram sync state tracking
003_add_expert_id.sql                 # Multi-expert support (CRITICAL)
004_add_expert_id_to_drift.sql        # Expert ID for drift analysis
005_add_unique_telegram_message_id.sql # Unique constraints (duplicate)
006_add_unique_telegram_message_id.sql # Fixed version
007_add_channel_username.sql          # Channel metadata
007_fix_unique_telegram_message_id.sql # Constraint fixes
008_fix_comment_unique_constraint.sql # Comment uniqueness fixes
```

**Missing Production Directories:**
- `/Users/andreysazonov/Documents/Projects/Experts_panel/data/` - Database directory (needs creation)
- `/Users/andreysazonov/Documents/Projects/Experts_panel/logs/` - Logs directory (needs creation)
- `/Users/andreysazonov/Documents/Projects/Experts_panel/ssl/` - SSL certificates (needs creation)
- `/Users/andreysazonov/Documents/Projects/Experts_panel/nginx/` - Production nginx configs (needs creation)

**Backend Dependencies Analysis (`/Users/andreysazonov/Documents/Projects/Experts_panel/backend/requirements.txt`):**
```txt
# Core framework
fastapi==0.115.0, uvicorn[standard]==0.31.0, pydantic==2.9.2

# Database & Async
sqlalchemy==2.0.35, aiosqlite==0.20.0, asyncpg==0.29.0

# OpenAI/OpenRouter Integration
openai==1.51.0, httpx==0.27.2

# SSE Streaming
sse-starlette==2.1.3

# Telegram API
telethon==1.36.0

# Development & Testing
pytest==8.3.3, ruff==0.6.9
```

### Current Production Gaps & Implementation Requirements

**Missing Production Components:**
1. **SSL/HTTPS Configuration**: No SSL certificate management or HTTPS setup
2. **Production Docker Compose**: Current docker-compose.yml configured for development
3. **Reverse Proxy Configuration**: No external nginx setup for SSL termination
4. **Environment Management**: No production-specific environment file management
5. **Deployment Automation**: No deployment scripts or VPS setup automation
6. **Security Hardening**: Missing production security configurations
7. **Monitoring Setup**: Limited logging and monitoring configuration

**Health Check Implementation Details:**
```python
# From backend/src/api/main.py lines 167-190
@router.get("/health", tags=["health"])
async def health_check():
    # Database connectivity test via SQLAlchemy
    # API key validation via OPENAI_API_KEY check
    return {
        "status": "healthy" if db_status == "healthy" and openai_configured else "degraded",
        "database": db_status,
        "openai_configured": openai_configured,
        "timestamp": time.time()
    }
```

**API Endpoint Production Readiness:**
- Main query endpoint: `POST /api/v1/query` with SSE streaming support
- Health check: `GET /health` with service status validation
- API documentation: `GET /api/docs` (should be disabled in production)
- Post retrieval: `GET /api/v1/posts/{post_id}` and `POST /api/v1/posts/by-ids`

### VPS Integration Requirements

**System Dependencies:**
```bash
# Required packages for Docker deployment
docker-ce docker-ce-cli containerd.io docker-compose-plugin
nginx (for SSL termination if external)
certbot (for Let's Encrypt certificates)
fail2ban (security)
ufw (firewall configuration)
```

**Network Configuration:**
- **Port Management**: 80 (HTTP), 443 (HTTPS), optional 8000 (direct backend access)
- **Firewall Rules**: Allow HTTP/HTTPS, SSH, restrict other ports
- **DNS Configuration**: A/AAAA records pointing to VPS IP
- **Reverse Proxy**: Nginx for SSL termination and load balancing

**SSL/HTTPS Setup:**
```nginx
# Nginx configuration for SSL termination
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    # Security headers and SSL configuration
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains";
    add_header X-Frame-Options DENY;
    add_header X-Content-Type-Options nosniff;
}
```

**Production Environment Setup:**
```bash
# Docker production deployment
docker-compose -f docker-compose.prod.yml up -d
# Health check validation
curl -f https://your-domain.com/health
# Log monitoring
docker-compose logs -f
```

### Production Deployment Architecture

**Container Orchestration Strategy:**
```yaml
# Production Docker Compose structure
services:
  nginx-reverse-proxy:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes: ["./ssl:/etc/ssl", "./nginx/nginx-prod.conf:/etc/nginx/conf.d"]

  backend-api:
    build: ./backend
    environment: ["ENVIRONMENT=production"]
    volumes: ["./data:/app/data", "./logs:/app/logs"]
    healthcheck: ["CMD", "curl", "-f", "http://localhost:8000/health"]

  frontend-app:
    build: ./frontend
    environment: ["REACT_APP_API_URL=https://your-domain.com/api"]
    depends_on: [backend-api]
```

**Service Dependencies:**
- **Frontend → Backend**: API communication via Nginx proxy
- **Backend → Database**: SQLite file access via mounted volume
- **Backend → External APIs**: OpenRouter API for LLM processing
- **Monitoring → Services**: Health check endpoints for all services

**Performance Considerations:**
- **Resource Limits**: CPU/memory constraints per container
- **Connection Pooling**: Database connection management
- **Caching Strategy**: Optional Redis for session management
- **Load Balancing**: Nginx for horizontal scaling readiness

### Implementation Guide & Best Practices

**Deployment Workflow:**
```bash
# 1. Environment preparation
git clone https://github.com/your-repo/experts-panel.git
cd experts-panel
cp .env.example .env.production
# Edit .env.production with production values

# 2. SSL certificate setup
sudo certbot certonly --standalone -d your-domain.com
sudo cp /etc/letsencrypt/live/your-domain.com/* ./ssl/

# 3. Database setup (copy from local development)
# Upload your latest experts.db from MacBook to ./data/experts.db
# Apply migrations if needed
docker-compose run --rm backend-api sqlite3 data/experts.db < backend/migrations/003_add_expert_id.sql

# 4. Production deployment
docker-compose -f docker-compose.prod.yml up -d
docker-compose ps  # Verify all services running
```

**Monitoring and Maintenance:**
```bash
# Health monitoring
curl https://your-domain.com/health
docker-compose exec backend-api curl -f http://localhost:8000/health

# Log management
docker-compose logs -f --tail=100 backend-api
docker-compose logs -f --tail=50 frontend-app

# Database replacement (if needed)
# Stop containers, replace ./data/experts.db with fresh version, restart
docker-compose -f docker-compose.prod.yml down
cp ~/Downloads/fresh-experts.db ./data/experts.db
docker-compose -f docker-compose.prod.yml up -d
```

**Troubleshooting Common Issues:**
- **Database Permissions**: Ensure volume mounts have correct permissions for appuser
- **API Connectivity**: Verify OpenRouter API key configuration
- **SSL Certificate Renewal**: Setup certbot auto-renewal cron job
- **Memory Limits**: Monitor container resource usage
- **VPS Recovery**: If VPS fails, redeploy from scratch with fresh database copy

**Security Hardening Checklist:**
- [ ] Change default passwords and API keys
- [ ] Configure firewall rules (UFW)
- [ ] Set up automatic security updates
- [ ] Enable fail2ban for SSH protection
- [ ] Regular security audits and log monitoring
- [ ] SSL/TLS certificate monitoring and renewal

### Technical Reference Details

#### Container Specifications

**Backend Container:**
- **Base Image**: `python:3.11-slim`
- **Working Directory**: `/app`
- **User**: `appuser` (non-root)
- **Exposed Port**: `8000`
- **Health Check**: `curl -f http://localhost:8000/health`
- **Volumes**: `./data:/app/data`, `./logs:/app/logs`

**Frontend Container:**
- **Base Image**: `nginx:alpine` (production stage)
- **Build Stage**: `node:18-alpine`
- **Exposed Port**: `80`
- **Static Files**: `/usr/share/nginx/html`
- **Configuration**: `/etc/nginx/conf.d/default.conf`

#### Production Environment Variables

**Backend Configuration:**
```bash
# Required
OPENROUTER_API_KEY=sk-your-production-key
DATABASE_URL=sqlite:///data/experts.db
ENVIRONMENT=production

# Security
SECRET_KEY=your-secure-secret-key-here
PRODUCTION_ORIGIN=https://your-domain.com

# Performance
MAX_POSTS_LIMIT=500
CHUNK_SIZE=20
REQUEST_TIMEOUT=300
LOG_LEVEL=INFO
```

**Frontend Configuration:**
```bash
# API communication
REACT_APP_API_URL=https://your-domain.com/api
GENERATE_SOURCEMAP=false  # Production build optimization
```

#### File Locations and Paths

**Configuration Files:**
- `docker-compose.yml` - Development Docker setup
- `docker-compose.prod.yml` - Production configuration (to be created)
- `.env.production` - Production environment variables
- `nginx/nginx-prod.conf` - Production Nginx reverse proxy configuration
- `ssl/` - SSL certificate directory

**Database and Data:**
- `data/experts.db` - SQLite database file (synced from MacBook)
- `logs/` - Application logs directory
- `backend/migrations/` - Database migration scripts

**Deployment Scripts:**
- `deploy.sh` - Simple deployment script for initial VPS setup (to be created)
- `update-ssl.sh` - SSL certificate renewal script (to be created)

#### API Endpoints and Health Checks

**Health Check Endpoint:**
```http
GET /health
Response: {
  "status": "healthy",
  "database": "healthy",
  "openrouter_configured": true,
  "timestamp": 1234567890
}
```

**Production API Endpoints:**
- `POST /api/v1/query` - Main query processing with SSE streaming
- `GET /health` - Service health status
- `GET /api/docs` - API documentation (development only)

## User Notes

<!-- Any specific notes or requirements from the developer -->

## Work Log
<!-- Updated as work progresses -->
- [2025-01-25] Context gathering completed, comprehensive analysis of existing Docker setup and deployment requirements
- [2025-01-25] Task simplified based on developer preferences:
  * Removed VPS backup strategy - using developer's MacBook + Dropbox + GitHub approach
  * Simplified database persistence to Docker bind mount volume
  * Removed automated backup scripts, keeping only deployment and SSL renewal scripts
  * Treated VPS as disposable infrastructure that can be redeployed from scratch