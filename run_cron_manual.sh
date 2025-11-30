#!/bin/bash

# Manual trigger for Cron Job (Sync + Drift)
# Usage: ./run_cron_manual.sh

echo "🚀 Starting Manual Cron Job Trigger..."

# Check if running from project root
if [ ! -d "backend" ]; then
    echo "❌ Error: Please run from project root directory"
    exit 1
fi

echo "📍 Working directory: $(pwd)"
echo "🐍 Python: $(which python3)"

# Run the job function via python -c
# We set PYTHONPATH to backend/ so imports work correctly
export PYTHONPATH=$PYTHONPATH:$(pwd)/backend

# Load .env from backend/ directory
if [ -f "backend/.env" ]; then
  echo "🔑 Loading environment variables from backend/.env..."
  set -a
  source backend/.env
  set +a
else
  echo "⚠️  Warning: backend/.env not found!"
fi

# Override DATABASE_URL to point to correct location from root (ABSOLUTE PATH)
export DATABASE_URL="sqlite:///$(pwd)/backend/data/experts.db"

echo "⏳ Running sync and drift analysis... (check backend/data/logs/cron_jobs.log for details)"

# Execute the function
python3 -c "from src.jobs import run_sync_and_drift_job; run_sync_and_drift_job()"

echo "✅ Manual trigger command finished."
echo "📄 Last 10 lines of cron log:"
tail -n 10 backend/data/logs/cron_jobs.log 2>/dev/null || echo "No log file yet."
