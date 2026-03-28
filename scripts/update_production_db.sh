#!/bin/bash

# ==============================================================================
# Script: update_production_db.sh
# Purpose: Run local sync, vectorize, drift analysis, and deploy to Fly.io
# Author: Experts Panel Team
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status

# Configuration
DB_PATH="backend/data/experts.db"
BACKUP_DIR="backend/data/backups"
REMOTE_DB_PATH="/app/data/experts.db"
REMOTE_BACKUP_PATH="/app/data/experts.db.backup"
APP_NAME="experts-panel"

# Ensure we are in project root
if [ ! -f "fly.toml" ]; then
    echo "❌ Error: Please run this script from the project root directory."
    exit 1
fi

# Create backup directory if not exists
mkdir -p "$BACKUP_DIR"

# Check for venv python or system python
PYTHON_CMD="python3"
if [ -f "backend/.venv/bin/python" ]; then
    PYTHON_CMD="backend/.venv/bin/python"
fi

# Load environment variables from backend/.env if it exists
if [ -f "backend/.env" ]; then
    echo "🔑 Loading environment variables from backend/.env..."
    set -a
    source backend/.env
    set +a
fi

# Set PYTHONPATH to include backend directory for imports
export PYTHONPATH=$PYTHONPATH:$(pwd)/backend
# Override DATABASE_URL to ensure we use the correct DB regardless of what's in .env
export DATABASE_URL="sqlite:///backend/data/experts.db"

echo "========================================================"
echo "🚀 STARTING PRODUCTION DB UPDATE SEQUENCE (9 steps)"
echo "========================================================"

# 1. Local Backup
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOCAL_BACKUP_FILE="$BACKUP_DIR/experts_local_pre_sync_$TIMESTAMP.db"
echo "📦 [1/9] Creating local backup..."
if [ -f "$DB_PATH" ]; then
    cp "$DB_PATH" "$LOCAL_BACKUP_FILE"
    echo "   ✅ Backup saved to: $LOCAL_BACKUP_FILE"
else
    echo "   ⚠️ Local DB not found at $DB_PATH. Skipping backup."
fi

# 2. Run Local Sync (Posts & Comments)
echo "🔄 [2/9] Running Local Sync (Posts & Comments)..."
if $PYTHON_CMD backend/sync_channel_multi_expert.py; then
    echo "   ✅ Local sync completed successfully."
else
    echo "   ❌ Sync failed. Aborting deployment."
    exit 1
fi

# 3. Run Database Migrations (skip already-applied via marker files)
echo "🗄️  [3/9] Running pending database migrations..."
MIGRATION_MARKER_DIR="$BACKUP_DIR/.migrations_applied"
mkdir -p "$MIGRATION_MARKER_DIR"
MIGRATIONS_APPLIED=0

for MIGRATION_FILE in backend/migrations/023_fts5_remove_metadata.sql; do
    MIGRATION_NAME=$(basename "$MIGRATION_FILE")
    MARKER_FILE="$MIGRATION_MARKER_DIR/$MIGRATION_NAME.done"
    if [ -f "$MARKER_FILE" ]; then
        continue
    fi
    if [ -f "$MIGRATION_FILE" ]; then
        echo "   📋 Applying $MIGRATION_NAME..."
        if sqlite3 "$DB_PATH" < "$MIGRATION_FILE"; then
            touch "$MARKER_FILE"
            MIGRATIONS_APPLIED=$((MIGRATIONS_APPLIED + 1))
            echo "   ✅ $MIGRATION_NAME applied."
        else
            echo "   ❌ $MIGRATION_NAME failed. Aborting."
            exit 1
        fi
    fi
done

if [ "$MIGRATIONS_APPLIED" -eq 0 ]; then
    echo "   ℹ️  No pending migrations."
else
    echo "   ✅ $MIGRATIONS_APPLIED migration(s) applied."
fi

# 4. Vectorize New Posts (Embeddings for Hybrid Search)
echo "🧮 [4/9] Vectorizing new posts (embeddings)..."
if $PYTHON_CMD backend/scripts/embed_posts.py --continuous; then
    echo "   ✅ Vectorization completed."
else
    echo "   ⚠️ Vectorization failed (non-critical). Continuing..."
fi

# 5. Run Drift Analysis
echo "🧠 [5/9] Running Drift Analysis (Gemini)..."
if $PYTHON_CMD backend/run_drift_service.py; then
    echo "   ✅ Drift analysis completed successfully."
else
    echo "   ❌ Drift analysis failed. Aborting deployment."
    exit 1
fi

# 6. Check/Wake up Fly.io Machine
echo "🌤️  [6/9] Checking remote machine status..."
MACHINE_STATUS=$(fly status --json | python3 -c "import sys, json; print(json.load(sys.stdin)['Machines'][0]['state'])")

if [ "$MACHINE_STATUS" == "stopped" ] || [ "$MACHINE_STATUS" == "suspended" ]; then
    echo "   💤 Machine is sleeping. Waking it up..."
    curl -s -o /dev/null --max-time 5 "https://$APP_NAME.fly.dev/health" || true
    fly machine start $(fly status --json | python3 -c "import sys, json; print(json.load(sys.stdin)['Machines'][0]['id'])") > /dev/null 2>&1
    echo "   ✅ Wake-up signal sent. Waiting 10s for boot..."
    sleep 10
else
    echo "   ✅ Machine is running."
fi

# 7. Remote Backup
echo "🛡️  [7/9] Creating remote backup on server..."
if fly ssh console -C "cp $REMOTE_DB_PATH $REMOTE_BACKUP_PATH"; then
    echo "   ✅ Remote backup created at $REMOTE_BACKUP_PATH"
else
    echo "   ⚠️ Failed to create remote backup (maybe file doesn't exist yet). Continuing."
fi

# 8. Upload New DB (Compressed)
echo "🚀 [8/9] Uploading fresh database (Compressed)..."
# Disable update check to prevent hanging on old machines
export FLY_NO_UPDATE_CHECK=1

# Delete current remote DB
fly ssh console -C "rm -f $REMOTE_DB_PATH" || true

# Compress locally
echo "   📦 Compressing database..."
gzip -c "$DB_PATH" > "$DB_PATH.gz"

# Upload compressed file
echo "   📤 Uploading compressed file..."
if fly sftp put "$DB_PATH.gz" "$REMOTE_DB_PATH.gz"; then
    echo "   ✅ Upload successful."
else
    echo "   ❌ Upload failed! Cleaning up..."
    rm -f "$DB_PATH.gz"
    exit 1
fi

# Decompress remotely
echo "   📦 Decompressing on server..."
if fly ssh console -C "gunzip -f $REMOTE_DB_PATH.gz"; then
    echo "   ✅ Decompression successful."
else
    echo "   ❌ Decompression failed!"
    rm -f "$DB_PATH.gz"
    exit 1
fi

# Clean up local compressed file
rm -f "$DB_PATH.gz"

# 9. Restart Application
echo "🔄 [9/9] Restarting application to load new DB..."
fly apps restart "$APP_NAME"
echo "   ✅ Restart command sent."

echo "========================================================"
echo "🎉 SUCCESS! Production database updated."
echo "========================================================"
