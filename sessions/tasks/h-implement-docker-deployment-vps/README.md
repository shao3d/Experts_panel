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
- [ ] Database persistence strategy with automated backups
- [ ] Environment variable management for production
- [ ] Health checks and monitoring configuration
- [ ] Automated deployment scripts and documentation
- [ ] Production security hardening and best practices

## Context Manifest

### How Experts Panel Currently Works: Architecture Overview

The Experts Panel is a sophisticated multi-expert query processing system with an eight-phase Map-Resolve-Reduce pipeline. The application consists of:

**Backend Service (FastAPI):**
- **Main Entry Point**: `backend/src/api/main.py` - FastAPI application with CORS, middleware, and health endpoints
- **Core Pipeline**: `backend/src/services/` directory containing eight-phase processing:
  1. **Map Phase** (`map_service.py`) - Semantic search with Qwen 2.5-72B, chunked processing with retry mechanism
  2. **Medium Scoring Phase** (`medium_scoring_service.py`) - Hybrid reranking with threshold ≥0.7 and top-5 selection
  3. **Differential Resolve Phase** (`simple_resolve_service.py`) - Database link expansion for HIGH posts only
  4. **Reduce Phase** (`reduce_service.py`) - Answer synthesis with Gemini 2.0 Flash
  5. **Language Validation Phase** (`language_validation_service.py`) - Language consistency validation and translation
  6. **Comment Groups** (`comment_group_map_service.py`) - Pre-analyzed drift matching with GPT-4o-mini
  7. **Comment Synthesis** (`comment_synthesis_service.py`) - Complementary insights extraction
  8. **Response Building** - Multi-expert response assembly

**Frontend Application (React/TypeScript):**
- **Build System**: Vite with TypeScript, React 18, and inline styling for MVP
- **Key Components**: Real-time SSE streaming, progress tracking, post reference clicking system
- **Production Serving**: Nginx reverse proxy with API proxying and static asset serving

**Database Architecture:**
- **Primary Database**: SQLite with SQLAlchemy 2.0 async support
- **Multi-Expert Support**: Complete data isolation via `expert_id` fields across all tables
- **Key Tables**: `posts`, `links`, `comments`, `comment_group_drift`
- **Migration System**: Sequential SQL migrations in `backend/migrations/` directory

**Multi-Model LLM Strategy:**
- **OpenRouter API Integration**: Multi-model approach with specific models per phase
- **Model Selection**: Qwen 2.5-72B (Map/Medium Scoring/Language Validation), Gemini 2.0 Flash (Reduce/Comment Synthesis), GPT-4o-mini (Comment Groups)

### Current Docker Configuration Analysis

**Existing Docker Infrastructure:**
The project already has basic Docker configuration that needs enhancement for production:

**Backend Dockerfile (`backend/Dockerfile`):**
```dockerfile
# Python 3.11-slim base image with security hardening
FROM python:3.11-slim
# Non-root user creation (appuser)
# Health check integration
# Volume mounting for /app/data
# Port 8000 exposure
# uvicorn startup command
```

**Frontend Dockerfile (`frontend/Dockerfile`):**
```dockerfile
# Multi-stage build: Node.js build + Nginx production
FROM node:18-alpine AS builder
FROM nginx:alpine AS production
# Static file serving with gzip compression
# API proxy configuration to backend service
```

**Docker Compose (`docker-compose.yml`):**
```yaml
# Two-service architecture: backend + frontend
# Network isolation via experts-panel-network
# Volume persistence for SQLite database
# Health checks and restart policies
# Port mapping: backend 8000, frontend 3000→80
```

**Current Limitations for Production:**
- No SSL/HTTPS configuration
- Missing production environment variable management
- No backup strategy for SQLite database
- Limited monitoring and logging configuration
- No automated deployment workflows
- Missing security hardening measures

### Database & Data Persistence Strategy

**SQLite Database Architecture:**
- **Database Path**: `data/experts.db` (mounted as Docker volume)
- **Connection String**: `sqlite:///data/experts.db` with `sqlite+aiosqlite:///data/experts.db` for async
- **Foreign Key Constraints**: Enabled via SQLAlchemy event listeners
- **Multi-Expert Data Isolation**: Complete separation via `expert_id` fields

**Critical Database Tables:**
```sql
-- Core content tables
posts (post_id, channel_id, expert_id, telegram_message_id, message_text, ...)
links (source_post_id, target_post_id, link_type, ...)
comments (comment_id, post_id, comment_text, ...)

-- Analysis tables
comment_group_drift (post_id, has_drift, drift_topics, expert_id, ...)
```

**Migration Requirements:**
```bash
# Required migrations for production deployment
sqlite3 data/experts.db < backend/migrations/003_add_expert_id.sql
sqlite3 data/experts.db < backend/migrations/004_add_expert_id_to_drift.sql
sqlite3 data/experts.db < backend/migrations/006_add_unique_telegram_message_id.sql
sqlite3 data/experts.db < backend/migrations/008_fix_comment_unique_constraint.sql
```

**Production Backup Strategy:**
- **Automated Backups**: Daily SQLite backups with retention policy
- **Backup Location**: Separate mounted volume or cloud storage
- **Recovery Process**: Database restoration from backup files
- **Migration Handling**: Apply migrations before data import

### Environment Configuration & Security

**Required Environment Variables:**
```bash
# Critical for system operation
OPENROUTER_API_KEY=sk-your-openrouter-api-key-here
DATABASE_URL=sqlite:///data/experts.db

# Production settings
PRODUCTION_ORIGIN=https://your-domain.com
API_HOST=0.0.0.0
API_PORT=8000
ENVIRONMENT=production
LOG_LEVEL=INFO

# Optional: Telegram API for synchronization
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=your-api-hash
TELEGRAM_CHANNEL=channel-name
```

**Security Considerations:**
- **API Key Management**: Secure storage via Docker secrets or environment files
- **CORS Configuration**: Production domain whitelisting
- **Non-root Containers**: Existing security hardening with appuser
- **Network Isolation**: Docker network segmentation
- **SSL/TLS**: HTTPS enforcement with certificate management

**CORS and Domain Configuration:**
```python
# From main.py - dynamic CORS origins
origins = [
    "http://localhost:3000", "http://localhost:3001", "http://localhost:5173",
    "http://127.0.0.1:3000", "http://127.0.0.1:3001", "http://127.0.0.1:5173",
]
production_origin = os.getenv("PRODUCTION_ORIGIN")  # Added dynamically
```

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
    volumes: ["./ssl:/etc/ssl", "./nginx.conf:/etc/nginx/conf.d"]

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

# 3. Database initialization
docker-compose run --rm backend-api python -m src.models.database init_db
# Apply migrations
docker-compose run --rm backend-api sqlite3 data/experts.db < migrations/003_add_expert_id.sql

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

# Database backups
docker-compose exec backend-api sqlite3 data/experts.db ".backup data/backup-$(date +%Y%m%d).db"
```

**Troubleshooting Common Issues:**
- **Database Permissions**: Ensure volume mounts have correct permissions
- **API Connectivity**: Verify OpenRouter API key configuration
- **SSL Certificate Renewal**: Setup certbot auto-renewal cron job
- **Memory Limits**: Monitor container resource usage
- **Network Issues**: Check Docker network configuration

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
- `nginx.conf` - Frontend Nginx configuration
- `ssl/` - SSL certificate directory

**Database and Data:**
- `data/experts.db` - SQLite database file
- `data/backups/` - Database backup directory
- `logs/` - Application logs directory
- `backend/migrations/` - Database migration scripts

**Deployment Scripts:**
- `deploy.sh` - Automated deployment script (to be created)
- `backup.sh` - Database backup script (to be created)
- `update-ssl.sh` - SSL certificate renewal (to be created)

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
