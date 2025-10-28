# Stage 1: Build Frontend
FROM node:18-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

# Set API URL for frontend build
ARG VITE_API_URL=https://experts-panel.fly.dev
ENV VITE_API_URL=$VITE_API_URL

COPY frontend/ .
RUN npm run build

# Stage 2: Build Backend and create final image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY backend/requirements.txt .

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy backend source code
COPY backend/ .

# Copy built frontend from the builder stage
COPY --from=frontend-builder /app/dist /app/static

# Create non-root user for security
RUN adduser --disabled-password --gecos '' appuser

# Create data directory for SQLite
RUN mkdir -p /app/data && chown -R appuser:appuser /app/data

USER appuser

# Expose port
EXPOSE 8000

# Add Docker health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Run the application
CMD ["sh", "-c", "uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000} --log-level info"]