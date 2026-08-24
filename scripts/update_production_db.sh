#!/bin/bash

# ==============================================================================
# Script: update_production_db.sh
# Purpose: Run the full DB pipeline (sync, vectorize, drift analysis) ON the
#          Oracle VM and deploy the result into the running panel container.
#
# Runs ENTIRELY on the Oracle VM (82.70.251.73). The Mac is a thin client:
#   ssh ubuntu@82.70.251.73
#   cd ~/apps/experts-panel/app && ./scripts/update_production_db.sh
# For long runs use tmux/nohup.
#
# Usage:
#   ./scripts/update_production_db.sh                     # full pipeline deploy
#   DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh    # skip sync/vectorize/
#                                                         # drift (deploy only)
#   ./scripts/update_production_db.sh --rollback          # restore prod DB from
#                                                         # the backup
#
# Layout on the VM:
#   ~/apps/experts-panel/app/backend/data/experts.db   — STAGING db (pipeline
#                                                        works here)
#   ~/apps/experts-panel/data/experts.db               — PROD db (mounted into
#                                                        the "panel" container)
#   ~/apps/experts-panel/docker-compose.vm.yml         — compose file
#
# Migration state is tracked INSIDE the database (schema_migrations table).
# Filesystem markers are deliberately not used: state must survive backups-dir
# cleanup and must reset together with the database itself.
# ==============================================================================

set -euo pipefail

# Configuration (paths are env-overridable for testing)
DB_PATH="${DB_PATH:-backend/data/experts.db}"
BACKUP_DIR="${BACKUP_DIR:-backend/data/backups}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-backend/migrations}"
DEPLOY_DIR="/home/ubuntu/apps/experts-panel"
PROD_DB_PATH="$DEPLOY_DIR/data/experts.db"
PROD_BACKUP_PATH="$DEPLOY_DIR/data/experts.db.backup"
PROD_TMP_PATH="$DEPLOY_DIR/data/experts.db.tmp"
PROD_GZ_TMP_PATH="$DEPLOY_DIR/data/experts.db.gz.tmp"
PROD_DATA_UID_GID="${PROD_DATA_UID_GID:-1000:1000}"   # container appuser
HEALTH_URL="${HEALTH_URL:-https://expa.beyondhorizon.dev/health}"
KEEP_LOCAL_BACKUPS="${KEEP_LOCAL_BACKUPS:-10}"     # deploy backups to keep locally
RESTART_HEALTH_TIMEOUT="${RESTART_HEALTH_TIMEOUT:-180}" # seconds to wait for /health after restart

# UPLOAD_WORK_DIR is set at runtime and cleaned by the EXIT trap.
UPLOAD_WORK_DIR=""

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

cleanup_prod_upload_artifacts() {
    sudo rm -f "$PROD_TMP_PATH" "$PROD_GZ_TMP_PATH" "$PROD_DB_PATH.gz" || true
}

wait_for_health() {
    local timeout_secs="$1"
    local waited=0
    echo "   ⏳ Waiting for $HEALTH_URL (max ${timeout_secs}s)..."
    while [ "$waited" -lt "$timeout_secs" ]; do
        if curl -sf --max-time 5 "$HEALTH_URL" >/dev/null 2>&1; then
            echo "   ✅ Health check passed."
            return 0
        fi
        sleep 5
        waited=$((waited + 5))
        echo "      ... still waiting (${waited}/${timeout_secs}s)"
    done
    echo "   ❌ Health endpoint did not return 200 within ${timeout_secs}s."
    return 1
}

restart_app_and_verify() {
    local context="$1"
    echo "🔄 Restarting application to load new DB..."
    sudo docker compose -f "$DEPLOY_DIR/docker-compose.vm.yml" \
        --env-file "$DEPLOY_DIR/.env.panel" restart panel
    echo "   ✅ Restart command sent."
    echo "🩺 Verifying application health after $context..."
    if wait_for_health "$RESTART_HEALTH_TIMEOUT"; then
        return 0
    fi
    echo "   ❌ Application is NOT healthy after restart."
    echo "      Inspect logs: sudo docker logs --tail 100 \$(sudo docker ps -qf name=panel-1)"
    echo "      Backup kept at: $PROD_BACKUP_PATH"
    echo "      Rollback with: ./scripts/update_production_db.sh --rollback"
    exit 1
}

# Keeps only the newest $1 deploy backups (experts_local_pre_sync_*.db),
# leaving other files in the backups dir untouched.
rotate_local_backups() {
    local keep="$1"
    local files
    files=()
    local f
    shopt -s nullglob
    for f in "$BACKUP_DIR"/experts_local_pre_sync_*.db; do
        files+=("$f")
    done
    shopt -u nullglob
    if [ "${#files[@]}" -le "$keep" ]; then
        return 0
    fi
    echo "   🗑️  Rotating local deploy backups (keeping last $keep)..."
    local count=0
    while IFS= read -r f; do
        count=$((count + 1))
        if [ "$count" -gt "$keep" ]; then
            echo "      removing $(basename "$f")"
            rm -f "$f"
        fi
    done < <(ls -1t "${files[@]}")
}

# Applies every migration in $MIGRATIONS_DIR not yet recorded in the
# schema_migrations table. On first run the table is bootstrapped by recording
# all currently present files as applied — the existing DB demonstrably has
# their effects, and a fresh DB is built from current models, for which
# "already applied" is also correct. Note: migration files manage their own
# transactions (several contain BEGIN TRANSACTION), so no outer transaction is
# possible; a record is inserted only after the file applied successfully.
run_pending_migrations() {
    echo "🗄️  [3/12] Running pending database migrations..."
    if [ ! -d "$MIGRATIONS_DIR" ]; then
        echo "   ❌ Migrations directory not found: $MIGRATIONS_DIR. Aborting."
        exit 1
    fi
    sqlite3 "$DB_PATH" "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT (datetime('now')));"

    local recorded
    recorded=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM schema_migrations;")
    if [ "$recorded" = "0" ]; then
        local f name count=0
        shopt -s nullglob
        for f in "$MIGRATIONS_DIR"/*.sql; do
            name=$(basename "$f")
            sqlite3 "$DB_PATH" "INSERT OR IGNORE INTO schema_migrations (name) VALUES ('$name');"
            count=$((count + 1))
        done
        shopt -u nullglob
        echo "   📋 Baseline: recorded $count existing migration(s) as applied (one-time bootstrap)."
    fi

    local applied=0 f name already
    shopt -s nullglob
    for f in "$MIGRATIONS_DIR"/*.sql; do
        name=$(basename "$f")
        already=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM schema_migrations WHERE name = '$name';")
        if [ "$already" -ge 1 ]; then
            continue
        fi
        echo "   📋 Applying $name..."
        if sqlite3 -bail "$DB_PATH" < "$f"; then
            sqlite3 "$DB_PATH" "INSERT INTO schema_migrations (name) VALUES ('$name');"
            if sqlite3 "$DB_PATH" "SELECT 1 FROM schema_migrations WHERE name = '$name';" | grep -q 1; then
                applied=$((applied + 1))
                echo "   ✅ $name applied."
            else
                echo "   ❌ $name: applied but could not be recorded. Aborting."
                exit 1
            fi
        else
            echo "   ❌ $name failed. Aborting deployment."
            echo "      If the file lacks internal transactions it may be partially applied;"
            echo "      inspect the DB before retrying."
            exit 1
        fi
    done
    shopt -u nullglob

    if [ "$applied" -eq 0 ]; then
        echo "   ℹ️  No pending migrations."
    else
        echo "   ✅ $applied migration(s) applied."
    fi
}

check_local_integrity() {
    echo "   🩺 Local SQLite integrity check on $DB_PATH..."
    local result
    result=$(sqlite3 "$DB_PATH" "PRAGMA integrity_check;" 2>&1 | head -n 1)
    if [ "$result" != "ok" ]; then
        echo "   ❌ Local DB integrity check failed: $result. Aborting before upload."
        exit 1
    fi
    echo "   ✅ Local DB integrity: ok."
}

# Guard: this script manages prod files under $DEPLOY_DIR and restarts the
# docker compose service, so it only makes sense on the VM itself.
ensure_running_on_vm() {
    if [ ! -f "$DEPLOY_DIR/docker-compose.vm.yml" ] || [ "$(hostname)" != "oracle-marseille-arm-dev" ]; then
        cat >&2 <<EOF
❌ This script must run ON the Oracle VM (oracle-marseille-arm-dev).
   From the Mac, use it as a thin client:

     ssh -t ubuntu@82.70.251.73
     cd ~/apps/experts-panel/app
     ./scripts/update_production_db.sh          # or: DB_UPLOAD_ONLY=1 ...

   Long runs: wrap in tmux (tmux new -A -s expadb).
EOF
        exit 1
    fi
}

# ==============================================================================
# Normal deploy
# ==============================================================================
do_deploy() {
    ensure_running_on_vm

    # Ensure we are in project root
    if [ ! -f "docker-compose.yml" ]; then
        echo "❌ Error: Please run this script from the project root directory ($DEPLOY_DIR/app)."
        exit 1
    fi

    PROJECT_ROOT="$(pwd)"
    ABS_DB_PATH="$PROJECT_ROOT/$DB_PATH"

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
        set +u
        source backend/.env
        set -u
    fi

    # Set PYTHONPATH to include backend directory for imports
    export PYTHONPATH="${PYTHONPATH:-}:$(pwd)/backend"
    # Override DATABASE_URL to ensure we use the correct DB regardless of what's in .env
    export DATABASE_URL="sqlite:///$ABS_DB_PATH"

    echo "========================================================"
    echo "🚀 STARTING PRODUCTION DB UPDATE SEQUENCE (12 steps)"
    echo "========================================================"

    # 1. Local Backup (consistent snapshot via SQLite Online Backup API)
    TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
    LOCAL_BACKUP_FILE="$BACKUP_DIR/experts_local_pre_sync_$TIMESTAMP.db"
    echo "📦 [1/12] Creating local backup snapshot..."
    if [ -f "$DB_PATH" ]; then
        if sqlite3 "$DB_PATH" ".backup '$LOCAL_BACKUP_FILE'"; then
            echo "   ✅ Consistent snapshot saved to: $LOCAL_BACKUP_FILE"
        else
            echo "   ⚠️ sqlite3 .backup failed; falling back to plain copy."
            cp "$DB_PATH" "$LOCAL_BACKUP_FILE"
        fi
    else
        echo "   ⚠️ Staging DB not found at $ABS_DB_PATH."
        if [ "${DB_UPLOAD_ONLY:-0}" != "1" ]; then
            echo "   ❌ Cannot run the pipeline without a staging DB. Aborting."
            exit 1
        fi
        echo "   ⏭️  DB_UPLOAD_ONLY=1 without staging DB: will promote PROD as-is (no-op deploy)."
    fi
    rotate_local_backups "$KEEP_LOCAL_BACKUPS"

    if [ "${DB_UPLOAD_ONLY:-0}" = "1" ]; then
        echo "⏭️  DB_UPLOAD_ONLY=1: skipping steps 2-7 (sync, migrations, vectorization, drift backfill, drift cleanup, drift analysis)."
    else
        # 2. Run Local Sync (Posts & Comments)
        echo "🔄 [2/12] Running Local Sync (Posts & Comments)..."
        if $PYTHON_CMD backend/sync_channel_multi_expert.py; then
            echo "   ✅ Local sync completed successfully."
        else
            echo "   ❌ Sync failed. Aborting deployment."
            exit 1
        fi

        # 3. Run Database Migrations (state tracked in schema_migrations table)
        run_pending_migrations

        # 4. Vectorize New Posts (Embeddings for Hybrid Search)
        echo "🧮 [4/12] Vectorizing new posts (embeddings)..."
        if $PYTHON_CMD backend/scripts/embed_posts.py --continuous; then
            echo "   ✅ Vectorization completed."
        else
            MISSING_EMB=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM posts p LEFT JOIN post_embeddings pe ON p.post_id = pe.post_id WHERE pe.post_id IS NULL AND p.message_text IS NOT NULL AND LENGTH(p.message_text) > 30;" 2>/dev/null || echo "?")
            echo "   ⚠️ Vectorization failed (non-critical). Continuing..."
            echo "   ⚠️ $MISSING_EMB post(s) have no embedding — hybrid search will be DEGRADED on production until the next successful deploy."
        fi

        # 5. Backfill Drift Embeddings (legacy comment_group_drift rows)
        echo "🧩 [5/12] Backfilling drift embeddings for legacy comment_group_drift rows (--limit 2000)..."
        if $PYTHON_CMD -m backend.scripts.maintenance.backfill_drift_embeddings --limit 2000; then
            echo "   ✅ Drift embedding backfill completed."
        else
            echo "   ⚠️ Drift embedding backfill failed (non-critical). Continuing..."
        fi

        # 6. Apply Drift Cleanup (legacy / newly-broken comment_group_drift rows)
        echo "🧹 [6/12] Applying drift cleanup (--apply, repair-or-NULL malformed drift_topics)..."
        if $PYTHON_CMD -m backend.scripts.maintenance.cleanup_malformed_drift --apply; then
            echo "   ✅ Drift cleanup completed."
        else
            echo "   ⚠️ Drift cleanup failed (non-critical). Continuing..."
        fi

        # 7. Run Drift Analysis
        echo "🧠 [7/12] Running Drift Analysis (Gemini via OpenRouter)..."
        if $PYTHON_CMD backend/run_drift_service.py; then
            echo "   ✅ Drift analysis completed successfully."
        else
            echo "   ❌ Drift analysis failed. Aborting deployment."
            exit 1
        fi
    fi

    # 8. Verify staging DB exists (pipeline may have been skipped)
    if [ "${DB_UPLOAD_ONLY:-0}" = "1" ] && [ ! -f "$ABS_DB_PATH" ]; then
        ABS_DB_PATH="$PROD_DB_PATH"
        echo "ℹ️  [8/12] No staging DB found; promoting current production DB unchanged (health/restart check only)."
    fi
    echo "🎯 [8/12] Staging DB ready: $ABS_DB_PATH ($(( $(wc -c < "$ABS_DB_PATH") / 1024 / 1024 )) MiB)"

    # 9. Prod Backup
    echo "🛡️  [9/12] Creating prod backup..."
    if [ -f "$PROD_DB_PATH" ]; then
        sudo rm -f "$PROD_BACKUP_PATH"
        sudo ln "$PROD_DB_PATH" "$PROD_BACKUP_PATH" 2>/dev/null || sudo cp "$PROD_DB_PATH" "$PROD_BACKUP_PATH"
        echo "   ✅ Prod backup created at $PROD_BACKUP_PATH"
    else
        echo "   ⚠️ Prod DB does not exist yet. Skipping backup."
    fi

    # 10. Stage New DB into prod dir (same filesystem: copy + verify + atomic mv)
    echo "🚀 [10/12] Promoting fresh database (compressed staged update)..."
    check_local_integrity

    UPLOAD_WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/experts-db-upload.XXXXXX")
    LOCAL_GZ_PATH="$UPLOAD_WORK_DIR/experts.db.gz"

    if command -v pigz >/dev/null 2>&1; then
        GZIP_BIN="pigz"
    else
        GZIP_BIN="gzip"
    fi
    echo "   🗜️  Compressing staging DB with $GZIP_BIN..."
    "$GZIP_BIN" -c "$ABS_DB_PATH" > "$LOCAL_GZ_PATH"

    LOCAL_DB_BYTES=$(wc -c < "$ABS_DB_PATH" | tr -d ' ')
    LOCAL_GZ_BYTES=$(wc -c < "$LOCAL_GZ_PATH" | tr -d ' ')
    LOCAL_GZ_SHA=$(sha256_file "$LOCAL_GZ_PATH")
    LOCAL_DB_KB=$(( (LOCAL_DB_BYTES + 1023) / 1024 ))
    LOCAL_GZ_KB=$(( (LOCAL_GZ_BYTES + 1023) / 1024 ))
    MIN_FREE_KB=$(( LOCAL_DB_KB + LOCAL_GZ_KB + 51200 ))

    cleanup_prod_upload_artifacts

    REMOTE_FREE_KB=$(df -Pk "$DEPLOY_DIR/data" | awk 'END {print $4}')

    if ! [[ "$REMOTE_FREE_KB" =~ ^[0-9]+$ ]]; then
        echo "   ❌ Could not determine free space on $DEPLOY_DIR/data."
        exit 1
    fi

    echo "   🧮 Free before deploy: $(( REMOTE_FREE_KB / 1024 )) MiB; DB size: $(( LOCAL_DB_KB / 1024 )) MiB; gzip: $(( LOCAL_GZ_KB / 1024 )) MiB"
    if [ "$REMOTE_FREE_KB" -lt "$MIN_FREE_KB" ]; then
        echo "   ❌ Not enough free space on $DEPLOY_DIR/data for a staged update."
        echo "      Need at least $(( MIN_FREE_KB / 1024 )) MiB free, found $(( REMOTE_FREE_KB / 1024 )) MiB."
        exit 1
    fi

    echo "   📤 Copying gzip into prod data dir..."
    rm -f "$PROD_GZ_TMP_PATH"
    if ! sudo cp "$LOCAL_GZ_PATH" "$PROD_GZ_TMP_PATH"; then
        echo "   ❌ Copy failed."
        cleanup_prod_upload_artifacts
        exit 1
    fi

    PROD_GZ_BYTES=$(sudo wc -c < "$PROD_GZ_TMP_PATH" | tr -d ' ')
    if [ "$PROD_GZ_BYTES" != "$LOCAL_GZ_BYTES" ]; then
        echo "   ❌ Copied gzip size mismatch. Expected $LOCAL_GZ_BYTES bytes, got $PROD_GZ_BYTES bytes."
        cleanup_prod_upload_artifacts
        exit 1
    fi

    PROD_GZ_SHA=$(sudo sha256sum "$PROD_GZ_TMP_PATH" | awk '{print $1}')
    if [ "$PROD_GZ_SHA" != "$LOCAL_GZ_SHA" ]; then
        echo "   ❌ Copied gzip SHA mismatch."
        echo "      Expected: $LOCAL_GZ_SHA"
        echo "      Got:      $PROD_GZ_SHA"
        cleanup_prod_upload_artifacts
        exit 1
    fi

    if gzip -t "$PROD_GZ_TMP_PATH"; then
        echo "   ✅ Gzip verified by size, SHA, and gzip test."
    else
        echo "   ❌ Gzip validation failed."
        cleanup_prod_upload_artifacts
        exit 1
    fi

    echo "   📦 Decompressing staged DB..."
    if sudo sh -c "rm -f $PROD_TMP_PATH && gzip -dc $PROD_GZ_TMP_PATH > $PROD_TMP_PATH"; then
        PROD_TMP_BYTES=$(sudo wc -c < "$PROD_TMP_PATH" | tr -d ' ')
    else
        echo "   ❌ Decompression failed."
        cleanup_prod_upload_artifacts
        exit 1
    fi

    if [ "$PROD_TMP_BYTES" != "$LOCAL_DB_BYTES" ]; then
        echo "   ❌ Decompressed DB size mismatch. Expected $LOCAL_DB_BYTES bytes, got $PROD_TMP_BYTES bytes."
        cleanup_prod_upload_artifacts
        exit 1
    fi

    echo "   🔎 Running SQLite integrity check on staged DB..."
    PROD_INTEGRITY=$(sudo python3 -c "import sqlite3; con=sqlite3.connect('$PROD_TMP_PATH'); print(con.execute('PRAGMA integrity_check').fetchone()[0])" | awk 'END {print $1}')
    if [ "$PROD_INTEGRITY" != "ok" ]; then
        echo "   ❌ SQLite integrity check failed: $PROD_INTEGRITY"
        cleanup_prod_upload_artifacts
        exit 1
    fi

    echo "   🔁 Replacing production database..."
    REPLACE_CMD="sudo rm -f $PROD_DB_PATH-wal $PROD_DB_PATH-shm && sudo mv -f $PROD_TMP_PATH $PROD_DB_PATH && sudo chown $PROD_DATA_UID_GID $PROD_DB_PATH && sudo rm -f $PROD_GZ_TMP_PATH"
    if bash -c "$REPLACE_CMD"; then
        echo "   ✅ Production database replaced."
    else
        echo "   ❌ Database replacement failed! Existing DB should still be available if mv did not run."
        exit 1
    fi

    # 11+12. Restart and verify health
    restart_app_and_verify "DB deploy"

    echo "========================================================"
    echo "🎉 SUCCESS! Production database updated and healthy."
    echo "========================================================"
}

# ==============================================================================
# Rollback: restore the backup created by the last deploy.
# The current production DB is snapshotted first, so the rollback itself
# can be undone.
# ==============================================================================
do_rollback() {
    ensure_running_on_vm

    echo "========================================================"
    echo "⏪ PRODUCTION DB ROLLBACK (restore from backup)"
    echo "========================================================"

    echo "🛡️ Checking backup..."
    if [ ! -f "$PROD_BACKUP_PATH" ] || [ ! -s "$PROD_BACKUP_PATH" ]; then
        echo "   ❌ No backup found at $PROD_BACKUP_PATH. Nothing to roll back to."
        exit 1
    fi
    echo "   ✅ Backup present ($(wc -c < "$PROD_BACKUP_PATH" | tr -d ' ') bytes)."

    PRE_ROLLBACK_SNAPSHOT="$DEPLOY_DIR/data/experts.db.pre_rollback_$(date +%Y%m%d_%H%M%S)"
    echo "📸 Snapshotting current production DB to $(basename "$PRE_ROLLBACK_SNAPSHOT") before overwriting..."
    if [ -f "$PROD_DB_PATH" ]; then
        sudo cp "$PROD_DB_PATH" "$PRE_ROLLBACK_SNAPSHOT" && sudo chown ubuntu:ubuntu "$PRE_ROLLBACK_SNAPSHOT"
        echo "   ✅ Pre-rollback snapshot created."
    else
        echo "   ⚠️ Could not snapshot the current DB; continuing (the backup itself stays intact)."
    fi

    echo "🔁 Restoring backup over production DB..."
    RESTORE_CMD="sudo rm -f $PROD_DB_PATH-wal $PROD_DB_PATH-shm && sudo cp $PROD_BACKUP_PATH $PROD_DB_PATH && sudo chown $PROD_DATA_UID_GID $PROD_DB_PATH"
    if ! bash -c "$RESTORE_CMD"; then
        echo "   ❌ Restore failed. Production DB was not modified."
        exit 1
    fi
    echo "   ✅ Production DB restored from backup."

    restart_app_and_verify "rollback"

    echo "========================================================"
    echo "🎉 ROLLBACK COMPLETE. Production is serving the backup DB."
    echo "   Pre-rollback DB kept at: $PRE_ROLLBACK_SNAPSHOT"
    echo "   Backup still intact at:  $PROD_BACKUP_PATH"
    echo "========================================================"
}

usage() {
    cat <<'USAGE'
Usage (run ON the Oracle VM; Mac is a thin client):
  ssh -t ubuntu@82.70.251.73
  cd ~/apps/experts-panel/app

  ./scripts/update_production_db.sh                    Full pipeline deploy
  DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh   Skip sync/vectorize/drift
  ./scripts/update_production_db.sh --rollback         Restore prod DB from backup
USAGE
}

main() {
    case "${1:-}" in
        --rollback)
            do_rollback
            ;;
        "")
            do_deploy
            ;;
        *)
            echo "❌ Unknown argument: $1"
            usage
            exit 1
            ;;
    esac
}

# Allow sourcing for tests without executing the deploy.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    main "$@"
fi
