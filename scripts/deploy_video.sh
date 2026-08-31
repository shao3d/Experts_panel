#!/bin/bash

# ==============================================================================
# Script: deploy_video.sh
# Purpose: Import a video JSON into the staging DB and safely promote it to
#          Production on the Oracle VM, reusing the tested production DB
#          deploy path.
# Usage: ./scripts/deploy_video.sh <path_to_json>
#
# Runs ENTIRELY on the Oracle VM, from the dev checkout:
#   ssh -t ubuntu@82.70.251.73
#   cd ~/apps/experts-panel/dev
#   ./scripts/deploy_video.sh path/to/video.json
#
# What it does:
#   1. Validates the JSON and importable input.
#   2. Imports segments into the STAGING DB (backend/data/experts.db) via
#      backend/scripts/import_video_json.py.
#   3. Optionally vectorizes fresh segments (embed_posts.py --continuous) so
#      hybrid search sees them immediately.
#   4. Delegates the actual production swap to the proven
#      ./scripts/update_production_db.sh DB_UPLOAD_ONLY=1 path, which backs up
#      prod, stages + verifies the DB (size/SHA/gzip/integrity), atomically
#      replaces it, restarts `panel` and waits for /health.
#
# This replaces the old Fly.io SFTP flow (upload to /app/data, fly ssh, fly
# apps restart), which is obsolete since production moved to the Oracle VM in
# 08.2026. Never run pipeline steps from the `app` checkout or from the Mac.
# ==============================================================================

set -euo pipefail

JSON_PATH="${1:-}"
DB_PATH="${DB_PATH:-backend/data/experts.db}"
DEPLOY_DIR="/home/ubuntu/apps/experts-panel"
DEV_CHECKOUT="$DEPLOY_DIR/dev"

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

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# ----------------------------------------------------------------------------
# Guards (mirror update_production_db.sh): video deploy is a production DB swap,
# so it only makes sense on the VM, from the dev checkout, in the project root.
# ----------------------------------------------------------------------------
ensure_running_on_vm() {
    if [ ! -f "$DEPLOY_DIR/docker-compose.vm.yml" ] || [ "$(hostname)" != "oracle-marseille-arm-dev" ]; then
        cat >&2 <<EOF
❌ This script must run ON the Oracle VM (oracle-marseille-arm-dev).
   From the Mac / other host, use it as a thin client:

     ssh -t ubuntu@82.70.251.73
     cd ~/apps/experts-panel/dev
     ./scripts/deploy_video.sh <path_to_json>
EOF
        exit 1
    fi
    if [ "$(pwd -P)" != "$DEV_CHECKOUT" ]; then
        cat >&2 <<EOF
❌ Run this command only from the development checkout:

     cd $DEV_CHECKOUT
     ./scripts/deploy_video.sh <path_to_json>

   The production checkout ($DEPLOY_DIR/app) is managed only by GitHub Actions.
EOF
        exit 1
    fi
    if [ ! -f "docker-compose.yml" ]; then
        error "Please run this script from the project root directory ($DEV_CHECKOUT)."
    fi
}

# 0. Validate input + guards
if [ -z "$JSON_PATH" ]; then
    echo "Usage: ./scripts/deploy_video.sh <path_to_json>"
    exit 1
fi
if [ ! -f "$JSON_PATH" ]; then
    error "JSON file not found: $JSON_PATH"
fi
ensure_running_on_vm

PYTHON_CMD="python3"
if [ -f "backend/.venv/bin/python" ]; then
    PYTHON_CMD="backend/.venv/bin/python"
fi
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/backend"

if [ ! -f "$DB_PATH" ]; then
    error "Staging DB not found at $DB_PATH. Run a full sync first (see docs/operations.md)."
fi

log "🚀 STARTING VIDEO DEPLOYMENT PIPELINE (Oracle VM)"
log "📂 Input File: $JSON_PATH"
log "🗄️  Staging DB: $DB_PATH"

# 1. Import Video JSON into staging DB
log "🧠 [1/4] Importing Video JSON into staging DB..."
if ! "$PYTHON_CMD" backend/scripts/import_video_json.py "$JSON_PATH"; then
    error "Import script failed. Staging DB left unchanged. Nothing was pushed to production."
fi
log "   ✅ Import successful."

# 2. Local integrity check before any promotion
log "🩺 [2/4] SQLite integrity check on staging DB..."
merge_integrity_ok=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | head -n 1)
if [ "$merge_integrity_ok" != "ok" ]; then
    error "Staging DB integrity check failed: $merge_integrity_ok. Aborting before deploy."
fi
log "   ✅ Staging DB integrity: ok."

# 3. Optionally vectorize the fresh video segments so hybrid search finds them
echo ""
read -r -p "🔎 Generate embeddings for new video segments now? (y/N) " do_embed
if [[ "${do_embed:-n}" =~ ^[Yy]$ ]]; then
    log "🧮 [3/4] Running embed_posts.py --continuous..."
    if "$PYTHON_CMD" backend/scripts/embed_posts.py --continuous; then
        log "   ✅ Vectorization completed."
    else
        warn "   ⚠️ Vectorization failed (non-critical). Hybrid search may be degraded until the next full DB deploy."
    fi
else
    log "⏭️  [3/4] Skipping embedding step. Run manually later if needed:"
    log "      python3 backend/scripts/embed_posts.py --continuous"
fi

# 4. Promote staging DB to production via the tested upload-only path.
#    update_production_db.sh handles prod backup, staged copy + verification
#    (size/SHA/gzip/integrity), atomic replace, `panel` restart and /health.
log "🚀 [4/4] Promoting staging DB to Production (update_production_db.sh DB_UPLOAD_ONLY=1)..."
DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh

log "=========================================================="
log "🎉 SUCCESS! Video imported and promoted to Production."
log "   Run './scripts/update_production_db.sh --rollback' to restore the"
log "   production DB from the backup created just before this deploy."
log "=========================================================="