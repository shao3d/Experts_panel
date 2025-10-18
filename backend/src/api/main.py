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
    """Root endpoint."""
    return {"message": "Hello World", "status": "running"}


@app.get("/health")
async def health():
    """Health check endpoint."""
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