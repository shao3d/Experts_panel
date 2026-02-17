#!/bin/bash

# ==============================================================================
# Script: deploy_video.sh
# Purpose: Import a video JSON into local DB and safely deploy to Production
# Usage: ./scripts/deploy_video.sh <path_to_json>
# Author: Gemini Architecture Team
# ==============================================================================

set -e # Exit immediately if a command exits with a non-zero status

# Configuration
JSON_PATH="$1"
DB_PATH="backend/data/experts.db"
REMOTE_DB_PATH="/app/data/experts.db"
APP_NAME="experts-panel"
BACKUP_DIR="backend/data/backups"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[WARNING] $1${NC}"
}

error() {
    echo -e "${RED}[ERROR] $1${NC}"
    exit 1
}

# 0. Validate Input
if [ -z "$JSON_PATH" ]; then
    error "Usage: ./scripts/deploy_video.sh <path_to_json>"
fi

if [ ! -f "$JSON_PATH" ]; then
    error "JSON file not found: $JSON_PATH"
fi

# Ensure we are in project root
if [ ! -f "fly.toml" ]; then
    error "Please run this script from the project root directory."
fi

mkdir -p "$BACKUP_DIR"

log "🚀 STARTING VIDEO DEPLOYMENT PIPELINE"
log "📂 Input File: $JSON_PATH"

# 1. Local Backup
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOCAL_BACKUP="$BACKUP_DIR/experts_pre_video_$TIMESTAMP.db"
log "📦 [1/5] Creating local backup..."
if [ -f "$DB_PATH" ]; then
    cp "$DB_PATH" "$LOCAL_BACKUP"
    log "   ✅ Backup saved: $LOCAL_BACKUP"
else
    warn "Local DB not found at $DB_PATH. Creating new one during import."
fi

# 2. Run Import Script
log "🧠 [2/5] Importing Video JSON into Local DB..."
# Check python command
PYTHON_CMD="python3"
if [ -f "backend/.venv/bin/python" ]; then
    PYTHON_CMD="backend/.venv/bin/python"
fi

export PYTHONPATH=$PYTHONPATH:$(pwd)/backend

if $PYTHON_CMD backend/scripts/import_video_json.py "$JSON_PATH"; then
    log "   ✅ Import successful."
else
    error "Import script failed! Restoring backup..."
    if [ -f "$LOCAL_BACKUP" ]; then
        cp "$LOCAL_BACKUP" "$DB_PATH"
        warn "   Restored database from backup."
    fi
    exit 1
fi

# 3. Compress DB for Upload
log "🗜️  [3/5] Compressing Database for Upload..."
GZ_PATH="$DB_PATH.gz"
gzip -c "$DB_PATH" > "$GZ_PATH"
log "   ✅ Database compressed: $(ls -lh $GZ_PATH | awk '{print $5}')"

# 4. Upload to Production
log "☁️  [4/5] Uploading to Fly.io Production..."

# Check machine status
try_machine_id=$(fly status --json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['Machines'][0]['id']) if data.get('Machines') else print('')")
try_machine_state=$(fly status --json | python3 -c "import sys, json; data=json.load(sys.stdin); print(data['Machines'][0]['state']) if data.get('Machines') else print('')")

if [ -z "$try_machine_id" ]; then
    error "No machines found in Fly.io app '$APP_NAME'. Is it deployed?"
fi

if [ "$try_machine_state" != "started" ]; then
    log "   💤 Machine is $try_machine_state. Waking it up..."
    fly machine start "$try_machine_id" > /dev/null
    log "   ✅ Start signal sent."
fi

# Robust SSH Wait Function
wait_for_ssh() {
    local max_retries=15
    local wait_sec=3
    log "   ⏳ Waiting for SSH connectivity..."
    
    for i in $(seq 1 $max_retries); do
        if fly ssh console -C "echo ready" > /dev/null 2>&1; then
            log "   ✅ SSH is ready."
            return 0
        fi
        echo -n "."
        sleep $wait_sec
    done
    
    echo ""
    error "Timed out waiting for SSH connectivity ($((max_retries * wait_sec))s). Check fly logs."
}

# Always verify SSH before SFTP
wait_for_ssh

log "   📤 Uploading compressed DB..."
if fly sftp put "$GZ_PATH" "$REMOTE_DB_PATH.gz"; then
    log "   ✅ Upload successful."
else
    rm -f "$GZ_PATH"
    error "SFTP Upload failed."
fi

# 5. Deploy (Unzip & Restart)
log "🔄 [5/5] Finalizing Deployment (Unzip & Restart)..."

log "   📦 Cleaning up old WAL files & Unzipping..."
# Critical: 
# 1. Delete WAL/SHM files to prevent corruption on DB swap
# 2. Gunzip (overwrite)
# 3. Fix permissions for appuser
REMOTE_CMD="rm -f $REMOTE_DB_PATH-wal $REMOTE_DB_PATH-shm && gunzip -f $REMOTE_DB_PATH.gz && chown appuser:appuser $REMOTE_DB_PATH"

if fly ssh console -C "$REMOTE_CMD"; then
    log "   ✅ Cleanup, Unzip & Permissions Fix successful."
else
    rm -f "$GZ_PATH"
    error "Remote operations failed."
fi

log "   🔄 Restarting application..."
if fly apps restart "$APP_NAME"; then
    log "   ✅ Restart command sent."
else
    warn "Restart command might have failed, check fly status."
fi

# Cleanup
rm -f "$GZ_PATH"

log "========================================================"
log "🎉 SUCCESS! Video imported and deployed to Production."
log "========================================================"
