# Stage 1: Build Frontend
FROM node:20-alpine AS frontend-builder
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm install

# Set API URL for frontend build
ARG VITE_API_URL=https://expa.beyondhorizon.dev
ENV VITE_API_URL=$VITE_API_URL

COPY frontend/ .
RUN npm run build

# Stage 2: Build Backend and create final image
FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Node.js runtime for the DeepSeek Harness CLI.
# Reddit Search V2 runs every LLM role (planner, answerability judge,
# reflection replanner, synthesis) through `dsh --profile headless`, and the
# backend deliberately has NO automatic cross-engine fallback: a missing `dsh`
# degrades Reddit search instead of silently calling another provider. So the
# binary ships with the image, pinned to the version the roles were measured
# against (see docs/architecture/reddit-service.md).
ARG DSH_VERSION=0.2.0-rc.2
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - \
    && apt-get install -y nodejs \
    && npm install -g "@deepseek-ai/dsh@${DSH_VERSION}" \
    && npm cache clean --force \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH="/app" \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    DSH_HOME="/home/appuser/.dsh" \
    DSH_PATCH_PATH="/app/deploy/dsh/reddit-llm.patch.yml"

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

# dsh home: the `headless` profile the Reddit roles boot, plus the writable
# session/storage directories dsh creates on first run. The CommandCode
# gateway key is NEVER baked here: the profile reads COMMANDCODE_API_KEY from
# the environment (deployment supplies it through the panel env file).
COPY backend/deploy/dsh/profile-headless/ /home/appuser/.dsh/profiles/headless/
# The overlay is read by `dsh` as appuser on every call: a checkout that keeps
# it 0600 (git does not track modes beyond +x) would fail the whole pipeline
# with EACCES, so the image normalizes it.
RUN chmod 0644 /app/deploy/dsh/reddit-llm.patch.yml \
    && mkdir -p /home/appuser/.dsh/sessions /home/appuser/.dsh/storages \
        /home/appuser/.dsh/attachments \
    && chown -R appuser:appuser /home/appuser/.dsh

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