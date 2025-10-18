"""Main FastAPI application with CORS and middleware configuration."""

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy import text

from .import_endpoints import router as import_router
from .comment_endpoints import router as comment_router
from .simplified_query_endpoint import router as query_router
from ..models.base import engine, Base

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    logger.info("Starting up Experts Panel API...")

    # Log environment variables status
    logger.info(f"Environment check:")
    logger.info(f"- OPENAI_API_KEY: {'configured' if os.getenv('OPENAI_API_KEY') else 'missing'}")
    logger.info(f"- PRODUCTION_ORIGIN: {os.getenv('PRODUCTION_ORIGIN', 'not set')}")
    logger.info(f"- Working directory: {os.getcwd()}")

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
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan
)

# Configure CORS
origins = [
    "http://localhost:3000",  # React development server
    "http://localhost:3001",  # React development server (alt port)
    "http://localhost:3002",  # Vite development server (alt port)
    "http://localhost:5173",  # Vite development server
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
    "http://127.0.0.1:5173",
]

# Add production origins from environment
production_origin = os.getenv("PRODUCTION_ORIGIN")
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


# Simple ping endpoint for basic connectivity test
@app.get("/ping", tags=["health"])
async def ping():
    """Simple ping endpoint."""
    logger.info("Ping requested")
    return {"message": "pong", "status": "alive"}

# Health check endpoint
@app.get("/health", tags=["health"])
async def health_check() -> Dict[str, Any]:
    """Health check endpoint - simple version for Railway."""

    # Always return success - let Railway know the app is running
    # Database and other services can be checked separately
    return {
        "status": "healthy",
        "version": "1.0.0",
        "message": "Application is running",
        "timestamp": time.time()
    }


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
# Simplified Map-Resolve+Reduce architecture (no GPT link evaluation)
app.include_router(query_router)


# Root redirect
@app.get("/", include_in_schema=False)
async def root():
    """Redirect root to API documentation."""
    return JSONResponse(
        content={
            "message": "Welcome to Experts Panel API",
            "documentation": "/api/docs",
            "health": "/health",
            "api_info": "/api/info"
        }
    )


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