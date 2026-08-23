#!/bin/bash

# ==============================================================================
# Script: update_production_db.sh
# Purpose: Run local sync, vectorize, drift analysis, and deploy the database
#          to production on the Oracle VM (docker compose behind Caddy).
# Author: Experts Panel Team
#
# Usage:
#   ./scripts/update_production_db.sh                     # full pipeline deploy
#   DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh    # skip local pipeline
#   ./scripts/update_production_db.sh --rollback          # restore prod DB from
#                                                         # the remote backup
#
# Migration state is tracked INSIDE the database (schema_migrations table).
# Filesystem markers are deliberately not used: state must survive backups-dir
# cleanup and must reset together with the database itself.
#
# Deployment target: ubuntu@82.70.251.73, data dir ~/apps/experts-panel/data,
# app runs as docker compose service "panel" (uid 1000) behind Caddy.
# ==============================================================================

set -euo pipefail

# Configuration (paths are env-overridable for testing)
DB_PATH="${DB_PATH:-backend/data/experts.db}"
BACKUP_DIR="${BACKUP_DIR:-backend/data/backups}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-backend/migrations}"
REMOTE_HOST="${REMOTE_HOST:-ubuntu@82.70.251.73}"
REMOTE_DB_DIR="/home/ubuntu/apps/experts-panel/data"
REMOTE_DB_PATH="$REMOTE_DB_DIR/experts.db"
REMOTE_BACKUP_PATH="$REMOTE_DB_DIR/experts.db.backup"
REMOTE_TMP_PATH="$REMOTE_DB_DIR/experts.db.tmp"
REMOTE_GZ_TMP_PATH="$REMOTE_DB_DIR/experts.db.gz.tmp"
REMOTE_DATA_UID_GID="${REMOTE_DATA_UID_GID:-1000:1000}"   # container appuser
HEALTH_URL="${HEALTH_URL:-https://expa.beyondhorizon.dev/health}"
KEEP_LOCAL_BACKUPS="${KEEP_LOCAL_BACKUPS:-10}"     # deploy backups to keep locally
RESTART_HEALTH_TIMEOUT="${RESTART_HEALTH_TIMEOUT:-180}" # seconds to wait for /health after restart
SSH_CONNECT_RETRIES="${SSH_CONNECT_RETRIES:-3}"

# UPLOAD_WORK_DIR is set at runtime and cleaned by the EXIT trap.
UPLOAD_WORK_DIR=""

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

remote_exec() {
    ssh -o BatchMode=yes "$REMOTE_HOST" "$@"
}

remote_stat_bytes() {
    remote_exec "if [ -e \"$1\" ]; then stat -c %s \"$1\"; else echo 0; fi" | awk 'END {print $1}'
}

cleanup_remote_upload_artifacts() {
    remote_exec "rm -f $REMOTE_TMP_PATH $REMOTE_GZ_TMP_PATH $REMOTE_DB_PATH.gz" || true
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
    remote_exec "cd /home/ubuntu/apps/experts-panel && sudo docker compose -f docker-compose.vm.yml --env-file .env.panel up -d --no-deps panel"
    echo "   ✅ Restart command sent."
    echo "🩺 Verifying application health after $context..."
    if wait_for_health "$RESTART_HEALTH_TIMEOUT"; then
        return 0
    fi
    echo "   ❌ Application is NOT healthy after restart."
    echo "      Inspect logs: ssh $REMOTE_HOST 'sudo docker logs --tail 100 \$(sudo docker ps -qf name=panel)'"
    echo "      Remote backup kept at: $REMOTE_BACKUP_PATH"
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

# Shared remote setup: SSH connectivity probe, data dir bootstrap, EXIT trap
# (clean local upload temp dir).
prepare_remote_session() {
    echo "   🌐 Checking SSH connectivity to $REMOTE_HOST..."
    local attempt=1
    until remote_exec "echo ok" >/dev/null 2>&1; do
        if [ "$attempt" -ge "$SSH_CONNECT_RETRIES" ]; then
            echo "   ❌ Cannot reach $REMOTE_HOST via SSH after $SSH_CONNECT_RETRIES attempt(s). Aborting."
            exit 1
        fi
        echo "      ... retry ($attempt/$SSH_CONNECT_RETRIES)"
        attempt=$((attempt + 1))
        sleep 3
    done
    remote_exec "mkdir -p $REMOTE_DB_DIR"
    trap 'rm -rf "${UPLOAD_WORK_DIR:-}"' EXIT
    echo "   ✅ Remote host reachable, data dir ready."
}

# ==============================================================================
# Normal deploy
# ==============================================================================
do_deploy() {
    # Ensure we are in project root
    if [ ! -f "docker-compose.yml" ]; then
        echo "❌ Error: Please run this script from the project root directory."
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
        echo "   ⚠️ Local DB not found at $DB_PATH. Skipping backup."
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
        #       Population runs once after migration 024 unlocks the fast
        #       cosine-similarity drift scoring path in comment_group_map_service.
        #       The script is idempotent: it only fills drift_embedding where NULL,
        #       so repeat deploys do no extra work.
        #       --limit 2000 bounds worst-case embedding API latency to ~5
        #       minutes per deploy (embeddings are served via OpenRouter,
        #       not Vertex). Remaining legacy rows are picked up by subsequent
        #       deploys until the legacy pool drains. drift_scheduler_service.py
        #       writes embeddings for new drift groups automatically.
        echo "🧩 [5/12] Backfilling drift embeddings for legacy comment_group_drift rows (--limit 2000)..."
        if $PYTHON_CMD -m backend.scripts.maintenance.backfill_drift_embeddings --limit 2000; then
            echo "   ✅ Drift embedding backfill completed."
        else
            echo "   ⚠️ Drift embedding backfill failed (non-critical). Continuing..."
        fi

        # 6. Apply Drift Cleanup (legacy / newly-broken comment_group_drift rows)
        #       Repairs rows where drift_topics has unquoted JSON object keys
        #       and NULLs+has_drift=0 rows whose JSON is unrecoverable.
        #       Runs BEFORE drift analysis so the drift service operates on
        #       already-clean drift_topics. Idempotent; a JSON manifest is
        #       written to backend/data/backups/drift_cleanup_<ts>.json for
        #       audit. NON-CRITICAL: broken rows are cosmetic and a future
        #       deploy re-attempts the cleanup.
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

    # 8. Check remote host connectivity
    echo "🌐 [8/12] Preparing remote host ($REMOTE_HOST)..."
    prepare_remote_session

    # 9. Remote Backup
    echo "🛡️  [9/12] Creating remote backup on server..."
    REMOTE_BACKUP_CMD="if [ -f $REMOTE_DB_PATH ]; then rm -f $REMOTE_BACKUP_PATH && (ln $REMOTE_DB_PATH $REMOTE_BACKUP_PATH || cp $REMOTE_DB_PATH $REMOTE_BACKUP_PATH); else exit 2; fi"
    if remote_exec "$REMOTE_BACKUP_CMD"; then
        echo "   ✅ Remote backup created at $REMOTE_BACKUP_PATH"
    else
        BACKUP_STATUS=$?
        if [ "$BACKUP_STATUS" -eq 2 ]; then
            echo "   ⚠️ Remote DB does not exist yet. Skipping backup."
        else
            echo "   ❌ Failed to create remote backup. Aborting before upload."
            exit 1
        fi
    fi

    # 10. Upload New DB (staged, compressed)
    echo "🚀 [10/12] Uploading fresh database (compressed staged upload)..."
    check_local_integrity

    UPLOAD_WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/experts-db-upload.XXXXXX")
    LOCAL_GZ_PATH="$UPLOAD_WORK_DIR/experts.db.gz"

    if command -v pigz >/dev/null 2>&1; then
        GZIP_BIN="pigz"
    else
        GZIP_BIN="gzip"
    fi
    echo "   🗜️  Compressing local DB with $GZIP_BIN before upload..."
    "$GZIP_BIN" -c "$DB_PATH" > "$LOCAL_GZ_PATH"

    LOCAL_DB_BYTES=$(wc -c < "$DB_PATH" | tr -d ' ')
    LOCAL_GZ_BYTES=$(wc -c < "$LOCAL_GZ_PATH" | tr -d ' ')
    LOCAL_GZ_SHA=$(sha256_file "$LOCAL_GZ_PATH")
    LOCAL_DB_KB=$(( (LOCAL_DB_BYTES + 1023) / 1024 ))
    LOCAL_GZ_KB=$(( (LOCAL_GZ_BYTES + 1023) / 1024 ))
    MIN_FREE_KB=$(( LOCAL_DB_KB + LOCAL_GZ_KB + 51200 ))

    # Clean up leftovers from previous failed uploads before checking space.
    cleanup_remote_upload_artifacts

    REMOTE_FREE_KB=$(remote_exec "df -Pk $REMOTE_DB_DIR" | awk 'END {print $4}')

    if ! [[ "$REMOTE_FREE_KB" =~ ^[0-9]+$ ]]; then
        echo "   ❌ Could not determine free space on $REMOTE_DB_DIR."
        exit 1
    fi

    echo "   🧮 Remote free before upload: $(( REMOTE_FREE_KB / 1024 )) MiB; DB size: $(( LOCAL_DB_KB / 1024 )) MiB; gzip: $(( LOCAL_GZ_KB / 1024 )) MiB"
    if [ "$REMOTE_FREE_KB" -lt "$MIN_FREE_KB" ]; then
        echo "   ❌ Not enough free space on $REMOTE_DB_DIR for a staged upload."
        echo "      Need at least $(( MIN_FREE_KB / 1024 )) MiB free, found $(( REMOTE_FREE_KB / 1024 )) MiB."
        echo "      Clean old backups/logs on the server before retrying."
        exit 1
    fi

    echo "   📤 Uploading gzip via scp..."
    remote_exec "rm -f $REMOTE_GZ_TMP_PATH"
    if ! scp -o BatchMode=yes -q "$LOCAL_GZ_PATH" "$REMOTE_HOST:$REMOTE_GZ_TMP_PATH"; then
        echo "   ❌ Upload failed."
        cleanup_remote_upload_artifacts
        exit 1
    fi

    REMOTE_GZ_BYTES=$(remote_stat_bytes "$REMOTE_GZ_TMP_PATH")
    if [ "$REMOTE_GZ_BYTES" != "$LOCAL_GZ_BYTES" ]; then
        echo "   ❌ Uploaded gzip size mismatch. Expected $LOCAL_GZ_BYTES bytes, got $REMOTE_GZ_BYTES bytes."
        cleanup_remote_upload_artifacts
        exit 1
    fi

    REMOTE_GZ_SHA=$(remote_exec "sha256sum $REMOTE_GZ_TMP_PATH | cut -d ' ' -f 1" | awk 'END {print $1}')
    if [ "$REMOTE_GZ_SHA" != "$LOCAL_GZ_SHA" ]; then
        echo "   ❌ Uploaded gzip SHA mismatch."
        echo "      Expected: $LOCAL_GZ_SHA"
        echo "      Got:      $REMOTE_GZ_SHA"
        cleanup_remote_upload_artifacts
        exit 1
    fi

    if remote_exec "gzip -t $REMOTE_GZ_TMP_PATH"; then
        echo "   ✅ Gzip upload verified by size, SHA, and gzip test."
    else
        echo "   ❌ Remote gzip validation failed."
        cleanup_remote_upload_artifacts
        exit 1
    fi

    echo "   📦 Decompressing staged DB on the server..."
    if remote_exec "rm -f $REMOTE_TMP_PATH && gzip -dc $REMOTE_GZ_TMP_PATH > $REMOTE_TMP_PATH"; then
        REMOTE_TMP_BYTES=$(remote_stat_bytes "$REMOTE_TMP_PATH")
    else
        echo "   ❌ Remote decompression failed."
        cleanup_remote_upload_artifacts
        exit 1
    fi

    if [ "$REMOTE_TMP_BYTES" != "$LOCAL_DB_BYTES" ]; then
        echo "   ❌ Decompressed DB size mismatch. Expected $LOCAL_DB_BYTES bytes, got $REMOTE_TMP_BYTES bytes."
        cleanup_remote_upload_artifacts
        exit 1
    fi

    echo "   🔎 Running SQLite integrity check on staged DB..."
    REMOTE_INTEGRITY=$(remote_exec "python3 -c \"import sqlite3; con=sqlite3.connect('$REMOTE_TMP_PATH'); print(con.execute('PRAGMA integrity_check').fetchone()[0])\"" | awk 'END {print $1}')
    if [ "$REMOTE_INTEGRITY" != "ok" ]; then
        echo "   ❌ SQLite integrity check failed: $REMOTE_INTEGRITY"
        cleanup_remote_upload_artifacts
        exit 1
    fi

    echo "   🔁 Replacing production database..."
    REMOTE_REPLACE_CMD="rm -f $REMOTE_DB_PATH-wal $REMOTE_DB_PATH-shm && mv -f $REMOTE_TMP_PATH $REMOTE_DB_PATH && sudo chown $REMOTE_DATA_UID_GID $REMOTE_DB_PATH && rm -f $REMOTE_GZ_TMP_PATH"
    if remote_exec "$REMOTE_REPLACE_CMD"; then
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
# Rollback: restore the remote backup created by the last deploy.
# The current production DB is snapshotted first, so the rollback itself
# can be undone.
# ==============================================================================
do_rollback() {
    if [ ! -f "docker-compose.yml" ]; then
        echo "❌ Error: Please run this script from the project root directory."
        exit 1
    fi

    echo "========================================================"
    echo "⏪ PRODUCTION DB ROLLBACK (restore from remote backup)"
    echo "========================================================"

    echo "🌐 Preparing remote host ($REMOTE_HOST)..."
    prepare_remote_session

    echo "🛡️ Checking remote backup..."
    REMOTE_BACKUP_BYTES=$(remote_stat_bytes "$REMOTE_BACKUP_PATH")
    if [ "$REMOTE_BACKUP_BYTES" = "0" ]; then
        echo "   ❌ No remote backup found at $REMOTE_BACKUP_PATH. Nothing to roll back to."
        exit 1
    fi
    echo "   ✅ Remote backup present ($REMOTE_BACKUP_BYTES bytes)."

    PRE_ROLLBACK_SNAPSHOT="$REMOTE_DB_DIR/experts.db.pre_rollback_$(date +%Y%m%d_%H%M%S)"
    echo "📸 Snapshotting current production DB to $(basename "$PRE_ROLLBACK_SNAPSHOT") before overwriting..."
    if remote_exec "if [ -f $REMOTE_DB_PATH ]; then cp $REMOTE_DB_PATH $PRE_ROLLBACK_SNAPSHOT; fi"; then
        echo "   ✅ Pre-rollback snapshot created."
    else
        echo "   ⚠️ Could not snapshot the current DB; continuing (the backup itself stays intact)."
    fi

    echo "🔁 Restoring backup over production DB..."
    RESTORE_CMD="rm -f $REMOTE_DB_PATH-wal $REMOTE_DB_PATH-shm && cp $REMOTE_BACKUP_PATH $REMOTE_DB_PATH && sudo chown $REMOTE_DATA_UID_GID $REMOTE_DB_PATH"
    if ! remote_exec "$RESTORE_CMD"; then
        echo "   ❌ Restore failed. Production DB was not modified."
        exit 1
    fi
    echo "   ✅ Production DB restored from backup."

    restart_app_and_verify "rollback"

    echo "========================================================"
    echo "🎉 ROLLBACK COMPLETE. Production is serving the backup DB."
    echo "   Pre-rollback DB kept at: $PRE_ROLLBACK_SNAPSHOT"
    echo "   Backup still intact at:  $REMOTE_BACKUP_PATH"
    echo "========================================================"
}

usage() {
    cat <<'USAGE'
Usage:
  ./scripts/update_production_db.sh                 Full pipeline deploy
  DB_UPLOAD_ONLY=1 ./scripts/update_production_db.sh  Skip local pipeline (upload only)
  ./scripts/update_production_db.sh --rollback      Restore prod DB from remote backup

Environment overrides:
  REMOTE_HOST=ubuntu@82.70.251.73     deployment target (default)
  HEALTH_URL=https://expa.beyondhorizon.dev/health
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
