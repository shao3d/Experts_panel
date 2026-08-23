#!/bin/bash

# ==============================================================================
# Script: update_production_db.sh
# Purpose: Run local sync, vectorize, drift analysis, and deploy to Fly.io
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
# ==============================================================================

set -euo pipefail

# Configuration (paths are env-overridable for testing)
DB_PATH="${DB_PATH:-backend/data/experts.db}"
BACKUP_DIR="${BACKUP_DIR:-backend/data/backups}"
MIGRATIONS_DIR="${MIGRATIONS_DIR:-backend/migrations}"
REMOTE_DB_PATH="/app/data/experts.db"
REMOTE_BACKUP_PATH="/app/data/experts.db.backup"
REMOTE_TMP_PATH="/app/data/experts.db.tmp"
REMOTE_GZ_TMP_PATH="/app/data/experts.db.gz.tmp"
REMOTE_CHUNK_PATH="/app/data/experts.db.upload_chunk"
APP_NAME="experts-panel"
HEALTH_URL="${HEALTH_URL:-https://experts-panel.fly.dev/health}"
UPLOAD_CHUNK_BYTES="${UPLOAD_CHUNK_BYTES:-2097152}"
UPLOAD_CHUNK_RETRIES="${UPLOAD_CHUNK_RETRIES:-5}"
RESTORE_AUTOSTOP="${RESTORE_AUTOSTOP:-stop}"       # fallback if current value can't be read
KEEP_LOCAL_BACKUPS="${KEEP_LOCAL_BACKUPS:-10}"     # deploy backups to keep locally
WAKE_STATE_TIMEOUT="${WAKE_STATE_TIMEOUT:-60}"     # seconds to wait for machine start
SSH_READY_RETRIES="${SSH_READY_RETRIES:-10}"       # ssh console probes after machine start
RESTART_HEALTH_TIMEOUT="${RESTART_HEALTH_TIMEOUT:-180}" # seconds to wait for /health after restart
export FLY_NO_UPDATE_CHECK=1

# MACHINE_ID / AUTOSTOP_RESTORE_VALUE / UPLOAD_WORK_DIR are set at runtime.
MACHINE_ID=""
AUTOSTOP_RESTORE_VALUE=""

sha256_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

remote_stat_bytes() {
    fly ssh console -C "sh -lc 'if [ -e \"$1\" ]; then stat -c %s \"$1\"; else echo 0; fi'" | awk 'END {print $1}'
}

cleanup_remote_upload_artifacts() {
    fly ssh console -C "sh -lc 'rm -f $REMOTE_TMP_PATH $REMOTE_GZ_TMP_PATH $REMOTE_CHUNK_PATH $REMOTE_DB_PATH.gz'" || true
}

# Prints the machine id; refuses to continue if the app does not have exactly
# one machine — the DB upload targets a single machine's volume and would
# silently miss the others.
get_machine_id() {
    fly status --json | python3 -c '
import sys, json
machines = json.load(sys.stdin).get("Machines") or []
if len(machines) != 1:
    sys.stderr.write("Expected exactly 1 Fly machine, found %d. "
                     "DB upload targets a single machine/volume.\n" % len(machines))
    sys.exit(1)
print(machines[0]["id"])
'
}

get_machine_state() {
    fly status --json | python3 -c "import sys, json; print(json.load(sys.stdin)['Machines'][0]['state'])"
}

# Best-effort read of the machine's current autostop value ("stop"/"suspend"/"off").
# Prints an empty string when it cannot be determined.
get_machine_autostop() {
    fly machine status --json "$1" --app "$APP_NAME" 2>/dev/null | python3 -c '
import sys, json
try:
    cfg = (json.load(sys.stdin) or {}).get("config") or {}
    print(cfg.get("autostop") or "")
except Exception:
    print("")
' || true
}

disable_autostop_for_deploy() {
    local machine_id="$1"
    echo "   🧷 Temporarily disabling Fly autostop during DB upload..."
    fly machine update "$machine_id" --app "$APP_NAME" --autostop=off --yes --skip-health-checks >/dev/null
    echo "   ✅ Autostop disabled for upload."
}

# Restores the autostop value captured before the deploy (falls back to
# RESTORE_AUTOSTOP if it could not be read), so a machine configured with
# "suspend" does not silently become "stop".
restore_autostop_after_deploy() {
    local machine_id="$1"
    local value="${AUTOSTOP_RESTORE_VALUE:-$RESTORE_AUTOSTOP}"
    if [ -z "$machine_id" ]; then
        return
    fi
    echo "   🧷 Restoring Fly autostop=$value..."
    fly machine update "$machine_id" --app "$APP_NAME" --autostop="$value" --yes --skip-health-checks >/dev/null || true
}

# Wakes the machine if needed, waits for the 'started' state (polling instead
# of a fixed sleep), then probes ssh console readiness.
ensure_machine_awake() {
    local machine_id="$1"
    local state
    state=$(get_machine_state)
    echo "   🌡️  Machine state: $state"
    if [ "$state" != "started" ]; then
        echo "   💤 Machine is not running. Waking it up..."
        curl -s -o /dev/null --max-time 5 "$HEALTH_URL" || true
        fly machine start "$machine_id" --app "$APP_NAME" > /dev/null 2>&1 || true
        local waited=0
        while [ "$waited" -lt "$WAKE_STATE_TIMEOUT" ]; do
            sleep 3
            waited=$((waited + 3))
            state=$(get_machine_state 2>/dev/null || echo unknown)
            if [ "$state" = "started" ]; then
                break
            fi
            echo "      ... waiting for machine to start (${waited}/${WAKE_STATE_TIMEOUT}s, state: $state)"
        done
    fi
    state=$(get_machine_state)
    if [ "$state" != "started" ]; then
        echo "   ❌ Machine did not reach 'started' state within ${WAKE_STATE_TIMEOUT}s (state: $state). Aborting."
        exit 1
    fi
    local probe=0
    until fly ssh console -C "echo ok" >/dev/null 2>&1; do
        probe=$((probe + 1))
        if [ "$probe" -ge "$SSH_READY_RETRIES" ]; then
            echo "   ❌ SSH console not ready after $SSH_READY_RETRIES probes. Aborting."
            exit 1
        fi
        sleep 3
    done
    echo "   ✅ Machine is running and SSH-ready."
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
    fly apps restart "$APP_NAME"
    echo "   ✅ Restart command sent."
    echo "🩺 Verifying application health after $context..."
    if wait_for_health "$RESTART_HEALTH_TIMEOUT"; then
        return 0
    fi
    echo "   ❌ Application is NOT healthy after restart."
    echo "      Inspect logs: fly logs --app $APP_NAME"
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

# Shared remote setup: single-machine check, wake, capture actual autostop
# value, disable autostop, install EXIT trap (restore autostop + clean local
# upload temp dir).
prepare_remote_session() {
    MACHINE_ID=$(get_machine_id)
    ensure_machine_awake "$MACHINE_ID"
    AUTOSTOP_RESTORE_VALUE="$(get_machine_autostop "$MACHINE_ID")"
    if [ -z "$AUTOSTOP_RESTORE_VALUE" ]; then
        echo "   ⚠️ Could not read current autostop; will restore '$RESTORE_AUTOSTOP' after deploy."
        AUTOSTOP_RESTORE_VALUE="$RESTORE_AUTOSTOP"
    else
        echo "   🧷 Current autostop captured: $AUTOSTOP_RESTORE_VALUE"
    fi
    disable_autostop_for_deploy "$MACHINE_ID"
    trap 'restore_autostop_after_deploy "$MACHINE_ID"; rm -rf "${UPLOAD_WORK_DIR:-}"' EXIT
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

    # 8. Check/Wake up Fly.io Machine
    echo "🌤️  [8/12] Preparing remote machine (single-machine check, wake, autostop)..."
    prepare_remote_session

    # 9. Remote Backup
    echo "🛡️  [9/12] Creating remote backup on server..."
    REMOTE_BACKUP_CMD="if [ -f $REMOTE_DB_PATH ]; then rm -f $REMOTE_BACKUP_PATH && (ln $REMOTE_DB_PATH $REMOTE_BACKUP_PATH || cp $REMOTE_DB_PATH $REMOTE_BACKUP_PATH); else exit 2; fi"
    if fly ssh console -C "sh -lc '$REMOTE_BACKUP_CMD'"; then
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

    # 10. Upload New DB (Resumable Staged)
    echo "🚀 [10/12] Uploading fresh database (compressed staged upload)..."
    check_local_integrity

    UPLOAD_WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/experts-db-upload.XXXXXX")
    LOCAL_GZ_PATH="$UPLOAD_WORK_DIR/experts.db.gz"
    LOCAL_CHUNK_PATH="$UPLOAD_WORK_DIR/chunk.bin"

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

    REMOTE_FREE_KB=$(fly ssh console -C "df -Pk /app/data" | awk 'END {print $4}')

    if ! [[ "$REMOTE_FREE_KB" =~ ^[0-9]+$ ]]; then
        echo "   ❌ Could not determine free space on /app/data."
        exit 1
    fi

    echo "   🧮 Remote free before upload: $(( REMOTE_FREE_KB / 1024 )) MiB; DB size: $(( LOCAL_DB_KB / 1024 )) MiB; gzip: $(( LOCAL_GZ_KB / 1024 )) MiB"
    if [ "$REMOTE_FREE_KB" -lt "$MIN_FREE_KB" ]; then
        echo "   ❌ Not enough free space on /app/data for a staged upload."
        echo "      Need at least $(( MIN_FREE_KB / 1024 )) MiB free, found $(( REMOTE_FREE_KB / 1024 )) MiB."
        echo "      Clean old backups/logs or increase the Fly volume before retrying."
        exit 1
    fi

    DIRECT_UPLOAD_OK=0
    if [ "${DB_UPLOAD_CHUNKED_ONLY:-0}" = "1" ]; then
        echo "   ⏭️  DB_UPLOAD_CHUNKED_ONLY=1: skipping direct SFTP upload."
    else
        echo "   📤 Uploading gzip in one SFTP transfer..."
        fly ssh console -C "sh -lc 'rm -f $REMOTE_GZ_TMP_PATH $REMOTE_CHUNK_PATH'"

        if fly sftp put "$LOCAL_GZ_PATH" "$REMOTE_GZ_TMP_PATH"; then
            REMOTE_GZ_BYTES=$(remote_stat_bytes "$REMOTE_GZ_TMP_PATH")
            if [ "$REMOTE_GZ_BYTES" = "$LOCAL_GZ_BYTES" ]; then
                DIRECT_UPLOAD_OK=1
                echo "   ✅ Direct gzip upload completed."
            else
                echo "   ⚠️ Direct upload size mismatch. Expected $LOCAL_GZ_BYTES bytes, got $REMOTE_GZ_BYTES bytes."
            fi
        else
            echo "   ⚠️ Direct gzip upload failed."
        fi
    fi

    if [ "$DIRECT_UPLOAD_OK" -ne 1 ]; then
        echo "   📤 Falling back to chunked upload in $UPLOAD_CHUNK_BYTES-byte chunks..."
        fly ssh console -C "sh -lc 'rm -f $REMOTE_GZ_TMP_PATH $REMOTE_CHUNK_PATH && : > $REMOTE_GZ_TMP_PATH'"

        UPLOADED_BYTES=0
        CHUNK_INDEX=0
        CHUNK_COUNT=$(( (LOCAL_GZ_BYTES + UPLOAD_CHUNK_BYTES - 1) / UPLOAD_CHUNK_BYTES ))

        while [ "$UPLOADED_BYTES" -lt "$LOCAL_GZ_BYTES" ]; do
            if ! dd if="$LOCAL_GZ_PATH" of="$LOCAL_CHUNK_PATH" bs="$UPLOAD_CHUNK_BYTES" skip="$CHUNK_INDEX" count=1 2>"$UPLOAD_WORK_DIR/dd_chunk.err"; then
                echo "   ❌ Failed to read local chunk $((CHUNK_INDEX + 1))/$CHUNK_COUNT (dd error):"
                cat "$UPLOAD_WORK_DIR/dd_chunk.err"
                cleanup_remote_upload_artifacts
                exit 1
            fi
            CHUNK_BYTES=$(wc -c < "$LOCAL_CHUNK_PATH" | tr -d ' ')
            EXPECTED_AFTER=$(( UPLOADED_BYTES + CHUNK_BYTES ))
            CHUNK_NUMBER=$(( CHUNK_INDEX + 1 ))
            echo "      chunk $CHUNK_NUMBER/$CHUNK_COUNT: $CHUNK_BYTES bytes"

            REMOTE_BEFORE=$(remote_stat_bytes "$REMOTE_GZ_TMP_PATH")
            if [ "$REMOTE_BEFORE" != "$UPLOADED_BYTES" ]; then
                echo "   ❌ Remote gzip stage size drifted. Expected $UPLOADED_BYTES bytes, got $REMOTE_BEFORE bytes."
                cleanup_remote_upload_artifacts
                exit 1
            fi

            ATTEMPT=1
            CHUNK_OK=0
            while [ "$ATTEMPT" -le "$UPLOAD_CHUNK_RETRIES" ]; do
                if fly sftp put "$LOCAL_CHUNK_PATH" "$REMOTE_CHUNK_PATH"; then
                    REMOTE_CHUNK_BYTES=$(remote_stat_bytes "$REMOTE_CHUNK_PATH")
                    if [ "$REMOTE_CHUNK_BYTES" = "$CHUNK_BYTES" ] && fly ssh console -C "sh -lc 'cat $REMOTE_CHUNK_PATH >> $REMOTE_GZ_TMP_PATH && rm -f $REMOTE_CHUNK_PATH'"; then
                        REMOTE_AFTER=$(remote_stat_bytes "$REMOTE_GZ_TMP_PATH")
                        if [ "$REMOTE_AFTER" = "$EXPECTED_AFTER" ]; then
                            CHUNK_OK=1
                            break
                        fi
                        echo "      ⚠️ Remote staged size mismatch after append: expected $EXPECTED_AFTER, got $REMOTE_AFTER"
                    else
                        echo "      ⚠️ Chunk size verification or append failed."
                    fi

                    REMOTE_AFTER_FAILURE=$(remote_stat_bytes "$REMOTE_GZ_TMP_PATH")
                    if [ "$REMOTE_AFTER_FAILURE" != "$UPLOADED_BYTES" ]; then
                        echo "   ❌ Remote gzip stage changed during a failed append. Cleaning up to avoid a corrupted staged file."
                        cleanup_remote_upload_artifacts
                        exit 1
                    fi
                else
                    echo "      ⚠️ Chunk upload attempt $ATTEMPT failed."
                fi

                fly ssh console -C "sh -lc 'rm -f $REMOTE_CHUNK_PATH'" || true
                ATTEMPT=$(( ATTEMPT + 1 ))
                sleep 2
            done

            if [ "$CHUNK_OK" -ne 1 ]; then
                echo "   ❌ Failed to upload chunk $CHUNK_NUMBER after $UPLOAD_CHUNK_RETRIES attempt(s). Cleaning up..."
                cleanup_remote_upload_artifacts
                exit 1
            fi

            UPLOADED_BYTES=$EXPECTED_AFTER
            CHUNK_INDEX=$(( CHUNK_INDEX + 1 ))
        done
    fi

    REMOTE_GZ_BYTES=$(remote_stat_bytes "$REMOTE_GZ_TMP_PATH")
    if [ "$REMOTE_GZ_BYTES" != "$LOCAL_GZ_BYTES" ]; then
        echo "   ❌ Uploaded gzip size mismatch. Expected $LOCAL_GZ_BYTES bytes, got $REMOTE_GZ_BYTES bytes."
        cleanup_remote_upload_artifacts
        exit 1
    fi

    REMOTE_GZ_SHA=$(fly ssh console -C "sh -lc 'sha256sum $REMOTE_GZ_TMP_PATH | cut -d \" \" -f 1'" | awk 'END {print $1}')
    if [ "$REMOTE_GZ_SHA" != "$LOCAL_GZ_SHA" ]; then
        echo "   ❌ Uploaded gzip SHA mismatch."
        echo "      Expected: $LOCAL_GZ_SHA"
        echo "      Got:      $REMOTE_GZ_SHA"
        cleanup_remote_upload_artifacts
        exit 1
    fi

    if fly ssh console -C "gzip -t $REMOTE_GZ_TMP_PATH"; then
        echo "   ✅ Gzip upload verified by size, SHA, and gzip test."
    else
        echo "   ❌ Remote gzip validation failed."
        cleanup_remote_upload_artifacts
        exit 1
    fi

    echo "   📦 Decompressing staged DB on Fly..."
    if fly ssh console -C "sh -lc 'rm -f $REMOTE_TMP_PATH && gzip -dc $REMOTE_GZ_TMP_PATH > $REMOTE_TMP_PATH'"; then
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
    REMOTE_INTEGRITY=$(fly ssh console -C "python3 -c \"import sqlite3; con=sqlite3.connect('$REMOTE_TMP_PATH'); print(con.execute('PRAGMA integrity_check').fetchone()[0])\"" | awk 'END {print $1}')
    if [ "$REMOTE_INTEGRITY" != "ok" ]; then
        echo "   ❌ SQLite integrity check failed: $REMOTE_INTEGRITY"
        cleanup_remote_upload_artifacts
        exit 1
    fi

    echo "   🔁 Replacing production database..."
    REMOTE_REPLACE_CMD="rm -f $REMOTE_DB_PATH-wal $REMOTE_DB_PATH-shm && mv -f $REMOTE_TMP_PATH $REMOTE_DB_PATH && chown appuser:appuser $REMOTE_DB_PATH && rm -f $REMOTE_GZ_TMP_PATH $REMOTE_CHUNK_PATH"
    if fly ssh console -C "sh -lc '$REMOTE_REPLACE_CMD'"; then
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

    echo "🌤️  Preparing remote machine..."
    prepare_remote_session

    echo "🛡️ Checking remote backup..."
    REMOTE_BACKUP_BYTES=$(remote_stat_bytes "$REMOTE_BACKUP_PATH")
    if [ "$REMOTE_BACKUP_BYTES" = "0" ]; then
        echo "   ❌ No remote backup found at $REMOTE_BACKUP_PATH. Nothing to roll back to."
        exit 1
    fi
    echo "   ✅ Remote backup present ($REMOTE_BACKUP_BYTES bytes)."

    PRE_ROLLBACK_SNAPSHOT="/app/data/experts.db.pre_rollback_$(date +%Y%m%d_%H%M%S)"
    echo "📸 Snapshotting current production DB to $(basename "$PRE_ROLLBACK_SNAPSHOT") before overwriting..."
    if fly ssh console -C "sh -lc 'if [ -f $REMOTE_DB_PATH ]; then cp $REMOTE_DB_PATH $PRE_ROLLBACK_SNAPSHOT; fi'"; then
        echo "   ✅ Pre-rollback snapshot created."
    else
        echo "   ⚠️ Could not snapshot the current DB; continuing (the backup itself stays intact)."
    fi

    echo "🔁 Restoring backup over production DB..."
    RESTORE_CMD="rm -f $REMOTE_DB_PATH-wal $REMOTE_DB_PATH-shm && cp $REMOTE_BACKUP_PATH $REMOTE_DB_PATH && chown appuser:appuser $REMOTE_DB_PATH"
    if ! fly ssh console -C "sh -lc '$RESTORE_CMD'"; then
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
