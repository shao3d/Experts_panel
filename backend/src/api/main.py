"""Minimal FastAPI application for Railway debugging."""

from fastapi import FastAPI
import time
import os
from sqlalchemy import create_engine, text

# Create minimal FastAPI application
app = FastAPI(
    title="Experts Panel API",
    version="1.0.0"
)


@app.get("/")
async def root():
    """Root endpoint - shows all available paths."""
    return {
        "message": "Hello World",
        "status": "running",
        "available_endpoints": [
            "/",
            "/health",
            "/api/health",
            "/api/v1/health",
            "/healthz",
            "/ready",
            "/ping"
        ],
        "timestamp": time.time()
    }


@app.get("/health")
@app.get("/api/health")
@app.get("/api/v1/health")
@app.get("/healthz")
@app.get("/ready")
async def health():
    """Health check endpoint - multiple paths for Railway compatibility."""

    # Check database connection
    db_status = "not_configured"
    database_url = os.getenv("DATABASE_URL", "")

    if database_url:
        try:
            # Simple connection test
            engine = create_engine(database_url.replace("postgresql://", "postgresql+asyncpg://", 1))
            with engine.connect() as conn:
                result = conn.execute(text("SELECT 1"))
                db_status = "connected"
        except Exception as e:
            db_status = f"error: {str(e)[:100]}"

    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": time.time(),
        "database": {
            "url_configured": bool(database_url),
            "status": db_status,
            "url_prefix": database_url.split("@")[0] + "@" if database_url else ""
        },
        "environment": os.getenv("RAILWAY_ENVIRONMENT", "unknown")
    }


@app.get("/ping")
async def ping():
    """Ping endpoint."""
    return {"message": "pong", "status": "alive"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)