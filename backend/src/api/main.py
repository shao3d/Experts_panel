"""Minimal FastAPI application for Railway debugging."""

from fastapi import FastAPI
import time

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
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": time.time()
    }


@app.get("/ping")
async def ping():
    """Ping endpoint."""
    return {"message": "pong", "status": "alive"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)