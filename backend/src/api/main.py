"""Main FastAPI application with CORS and middleware configuration."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any, List
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request, HTTPException, status, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text

from .import_endpoints import router as import_router
from .comment_endpoints import router as comment_router
from .simplified_query_endpoint import router as query_router
from .log_endpoints import router as log_router
from ..models.base import engine, Base
from .. import config

ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
IS_PRODUCTION = ENVIRONMENT.lower() == "production"

# Configure logging - explicit FileHandler setup to work with uvicorn
root_logger = logging.getLogger()
root_logger.setLevel(config.LOG_LEVEL.upper())

# Create file handler for backend logs
os.makedirs(os.path.dirname(config.BACKEND_LOG_FILE), exist_ok=True)
file_handler = logging.FileHandler(config.BACKEND_LOG_FILE, mode='a')
formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
file_handler.setFormatter(formatter)
file_handler.setLevel(config.LOG_LEVEL.upper())

# Add file handler if not already present (prevents duplication on --reload)
if not any(isinstance(h, logging.FileHandler) and
           hasattr(h, 'baseFilename') and
           h.baseFilename and
           h.baseFilename.endswith(config.BACKEND_LOG_FILE)
           for h in root_logger.handlers):
    root_logger.addHandler(file_handler)

logger = logging.getLogger(__name__)

# Configure frontend logger
frontend_logger = logging.getLogger("frontend")
os.makedirs(os.path.dirname(config.FRONTEND_LOG_FILE), exist_ok=True)
handler = logging.FileHandler(config.FRONTEND_LOG_FILE, mode='a')
formatter = logging.Formatter('%(asctime)s - %(message)s')
handler.setFormatter(formatter)
# Avoid adding handlers multiple times on reload
if not frontend_logger.handlers:
    frontend_logger.addHandler(handler)
frontend_logger.setLevel(config.LOG_LEVEL.upper())
frontend_logger.propagate = False # Prevent duplicate logs in backend.log


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting up Experts Panel API...")

    # Create database tables if they don't exist
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables verified/created")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        # Don't prevent startup, but log the error
    
    yield

    # Shutdown
    logger.info("Shutting down Experts Panel API...")


# Create FastAPI application
app = FastAPI(
    title="Experts Panel API",
    description="Map-Resolve-Reduce pipeline for Telegram channel analysis",
    version="1.0.0",
    docs_url=None if IS_PRODUCTION else "/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
    debug=not IS_PRODUCTION,
)

# Configure CORS
production_origin = os.getenv("PRODUCTION_ORIGIN")

if IS_PRODUCTION:
    origins = [production_origin] if production_origin else []
else:
    origins = [
        "http://localhost:3000",  # React development server
        "http://localhost:3001",  # React development server (alt port)
        "http://localhost:3002",  # Vite development server (alt port)
        "http://localhost:3003",  # React development server (additional port)
        "http://localhost:5173",  # Vite development server
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3002",
        "http://127.0.0.1:3003",
        "http://127.0.0.1:5173",
    ]
    if production_origin:
        origins.append(production_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)


# Request ID middleware
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    """Add unique request ID to each request."""
    request_id = str(uuid.uuid4())
    request.state.request_id = request_id

    start_time = time.time()

    response = await call_next(request)

    process_time = time.time() - start_time
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Process-Time"] = str(process_time)

    # Log request details
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s - "
        f"ID: {request_id}"
    )

    return response


# Exception handlers
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle HTTP exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "http_error",
            "message": exc.detail,
            "request_id": request_id
        },
        headers={"X-Request-ID": request_id}
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    request_id = getattr(request.state, "request_id", "unknown")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": "validation_error",
            "message": "Invalid request data",
            "details": exc.errors(),
            "request_id": request_id
        },
        headers={"X-Request-ID": request_id}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    request_id = getattr(request.state, "request_id", "unknown")
    logger.error(f"Unexpected error for request {request_id}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": "internal_error",
            "message": "An unexpected error occurred",
            "request_id": request_id
        },
        headers={"X-Request-ID": request_id}
    )


# Database dependency
def get_db():
    """Database session dependency."""
    from ..models.base import SessionLocal
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Pydantic model for expert info
class ExpertStats(BaseModel):
    posts_count: int
    comments_count: int

class ExpertInfo(BaseModel):
    """Expert information for frontend."""
    expert_id: str
    display_name: str
    channel_username: str
    stats: ExpertStats


# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint."""
    try:
        # Check database connection
        from ..models.base import SessionLocal
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db.close()
        db_status = "healthy"
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        db_status = "unhealthy"

    # Check API key (Google AI Studio)
    api_key_configured = bool(config.GOOGLE_AI_STUDIO_API_KEYS)

    return {
        "status": "healthy" if db_status == "healthy" and api_key_configured else "degraded",
        "version": "1.0.0",
        "database": db_status,
        "api_key_configured": api_key_configured,
        "google_ai_keys_count": len(config.GOOGLE_AI_STUDIO_API_KEYS),
        "timestamp": time.time()
    }


# Experts endpoint
@app.get("/api/v1/experts", response_model=List[ExpertInfo], tags=["experts"])
def get_experts(db = Depends(get_db)) -> List[ExpertInfo]:
    """Get all experts from expert_metadata table with dynamic stats.

    Returns list of experts for dynamic frontend loading.
    Added in Migration 009 as part of expert metadata centralization.
    Updated to include real-time post and comment counts.
    """
    from ..models.expert import Expert
    from ..models.post import Post
    from ..models.comment import Comment
    from sqlalchemy import func

    # Fetch experts
    experts = db.query(Expert).order_by(Expert.expert_id).all()
    
    # Calculate stats for each expert
    # We do this in code to avoid complex group by logic with potential zero counts
    # Ideally this would be a single optimized query, but for < 20 experts this is fine
    results = []
    
    for e in experts:
        # Count posts
        posts_count = db.query(func.count(Post.post_id)).filter(Post.expert_id == e.expert_id).scalar() or 0
        
        # Count comments (join through posts)
        comments_count = db.query(func.count(Comment.comment_id)).join(Post, Comment.post_id == Post.post_id).filter(Post.expert_id == e.expert_id).scalar() or 0
        
        results.append(ExpertInfo(
            expert_id=e.expert_id,
            display_name=e.display_name,
            channel_username=e.channel_username,
            stats=ExpertStats(
                posts_count=posts_count,
                comments_count=comments_count
            )
        ))

    return results


# API info endpoint
@app.get("/api/info", tags=["info"])
async def api_info() -> Dict[str, Any]:
    """API information endpoint."""
    return {
        "name": "Experts Panel API",
        "version": "1.0.0",
        "description": "Map-Resolve-Reduce pipeline for Telegram channel analysis",
        "features": [
            "Map-Resolve-Reduce pipeline",
            "Server-Sent Events streaming",
            "Expert comments integration",
            "Link-based context enrichment",
            "GPT-4o-mini powered synthesis"
        ],
        "endpoints": {
            "query": "/api/query",
            "health": "/health",
            "docs": "/api/docs",
            "openapi": "/api/openapi.json"
        }
    }


# Include routers
app.include_router(import_router, prefix="/api/v1")
app.include_router(comment_router, prefix="/api/v1")
app.include_router(log_router)
# Simplified Map-Resolve+Reduce architecture (no GPT link evaluation)
app.include_router(query_router)

# Mount static files to serve frontend
# This must be LAST, after all API routers
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")
else:
    logger.warning("Static directory not found, frontend will not be served")




if __name__ == "__main__":
    import uvicorn

    # Development server configuration
    uvicorn.run(
        "src.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
