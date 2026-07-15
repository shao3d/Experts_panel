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
REMOTE_TMP_PATH="/app/data/experts.db.tmp"
REMOTE_GZ_TMP_PATH="/app/data/experts.db.gz.tmp"
REMOTE_CHUNK_PATH="/app/data/experts.db.upload_chunk"
APP_NAME="experts-panel"
UPLOAD_CHUNK_BYTES="${UPLOAD_CHUNK_BYTES:-2097152}"
UPLOAD_CHUNK_RETRIES="${UPLOAD_CHUNK_RETRIES:-5}"
RESTORE_AUTOSTOP="${RESTORE_AUTOSTOP:-stop}"
export FLY_NO_UPDATE_CHECK=1

# Ensure we are in project root
if [ ! -f "fly.toml" ]; then
    echo "❌ Error: Please run this script from the project root directory."
    exit 1
fi

PROJECT_ROOT="$(pwd)"
ABS_DB_PATH="$PROJECT_ROOT/$DB_PATH"

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

get_machine_id() {
    fly status --json | python3 -c "import sys, json; print(json.load(sys.stdin)['Machines'][0]['id'])"
}

get_machine_state() {
    fly status --json | python3 -c "import sys, json; print(json.load(sys.stdin)['Machines'][0]['state'])"
}

disable_autostop_for_deploy() {
    local machine_id="$1"
    echo "   🧷 Temporarily disabling Fly autostop during DB upload..."
    fly machine update "$machine_id" --app "$APP_NAME" --autostop=off --yes --skip-health-checks >/dev/null
    echo "   ✅ Autostop disabled for upload."
}

restore_autostop_after_deploy() {
    local machine_id="$1"
    if [ -z "$machine_id" ]; then
        return
    fi
    echo "   🧷 Restoring Fly autostop=$RESTORE_AUTOSTOP..."
    fly machine update "$machine_id" --app "$APP_NAME" --autostop="$RESTORE_AUTOSTOP" --yes --skip-health-checks >/dev/null || true
}

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
export DATABASE_URL="sqlite:///$ABS_DB_PATH"

echo "========================================================"
echo "🚀 STARTING PRODUCTION DB UPDATE SEQUENCE (11 steps)"
echo "========================================================"

# 1. Local Backup
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
LOCAL_BACKUP_FILE="$BACKUP_DIR/experts_local_pre_sync_$TIMESTAMP.db"
echo "📦 [1/11] Creating local backup..."
if [ -f "$DB_PATH" ]; then
    cp "$DB_PATH" "$LOCAL_BACKUP_FILE"
    echo "   ✅ Backup saved to: $LOCAL_BACKUP_FILE"
else
    echo "   ⚠️ Local DB not found at $DB_PATH. Skipping backup."
fi

if [ "${DB_UPLOAD_ONLY:-0}" = "1" ]; then
    echo "⏭️  DB_UPLOAD_ONLY=1: skipping steps 2-5.5 (sync, migrations, vectorization, drift backfill, drift analysis, drift cleanup)."
else
    # 2. Run Local Sync (Posts & Comments)
    echo "🔄 [2/11] Running Local Sync (Posts & Comments)..."
    if $PYTHON_CMD backend/sync_channel_multi_expert.py; then
        echo "   ✅ Local sync completed successfully."
    else
        echo "   ❌ Sync failed. Aborting deployment."
        exit 1
    fi

    # 3. Run Database Migrations (skip already-applied via marker files)
    echo "🗄️  [3/11] Running pending database migrations..."
    MIGRATION_MARKER_DIR="$BACKUP_DIR/.migrations_applied"
    mkdir -p "$MIGRATION_MARKER_DIR"
    MIGRATIONS_APPLIED=0

    for MIGRATION_FILE in backend/migrations/023_fts5_remove_metadata.sql backend/migrations/024_drift_embedding.sql; do
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
    echo "🧮 [4/11] Vectorizing new posts (embeddings)..."
    if $PYTHON_CMD backend/scripts/embed_posts.py --continuous; then
        echo "   ✅ Vectorization completed."
    else
        echo "   ⚠️ Vectorization failed (non-critical). Continuing..."
    fi

    # 4.5. Backfill Drift Embeddings (legacy comment_group_drift rows)
    #       Population runs once after migration 024 unlocks the fast
    #       cosine-similarity drift scoring path in comment_group_map_service.
    #       The script is idempotent: it only fills drift_embedding where NULL,
    #       so repeat deploys do no extra work.
    #       --limit 2000 bounds worst-case Vertex latency to ~5 minutes per
    #       deploy (measured ~0.2s per row / ~9s per 50-row batch on local
    #       us-central1). Remaining legacy rows are picked up by subsequent
    #       deploys (each applies the same --limit 2000 cap) until the legacy
    #       pool drains. drift_scheduler_service.py writes embeddings for new
    #       drift groups automatically, so only pre-migration-024 legacy rows
    #       ever need this step.
    echo "🧩 [4.5/11] Backfilling drift embeddings for legacy comment_group_drift rows (--limit 2000)..."
    if $PYTHON_CMD -m backend.scripts.maintenance.backfill_drift_embeddings --limit 2000; then
        echo "   ✅ Drift embedding backfill completed."
    else
        echo "   ⚠️ Drift embedding backfill failed (non-critical). Continuing..."
    fi

    # 5. Run Drift Analysis
    echo "🧠 [5/11] Running Drift Analysis (Gemini)..."
    if $PYTHON_CMD backend/run_drift_service.py; then
        echo "   ✅ Drift analysis completed successfully."
    else
        echo "   ❌ Drift analysis failed. Aborting deployment."
        exit 1
    fi

    # 5.5. Apply Drift Cleanup (legacy / newly-broken comment_group_drift rows)
    #       Runs cleanup_malformed_drift --apply to repair rows where
    #       drift_topics has unquoted JSON object keys (regex-fixable, then
    #       re-rendered strictly) and to NULL+has_drift=0 any rows whose
    #       JSON is unrecoverable (truncated strings, shell-expansion
    #       artifacts, etc.).
    #       The script is idempotent — running on an already-clean DB is a
    #       no-op. A JSON manifest is written to
    #       backend/data/backups/drift_cleanup_<ts>.json for audit regardless
    #       of whether anything was changed.
    #       Marked NON-CRITICAL: a failure here only logs a warning and the
    #       deploy continues, since broken rows are cosmetic (they exit the
    #       drift scoring chain via has_drift=0 either way, and a future
    #       deploy will re-attempt the cleanup).
    echo "🧹 [5.5/11] Applying drift cleanup (--apply, repair-or-NULL malformed drift_topics)..."
    if $PYTHON_CMD -m backend.scripts.maintenance.cleanup_malformed_drift --apply; then
        echo "   ✅ Drift cleanup completed."
    else
        echo "   ⚠️ Drift cleanup failed (non-critical). Continuing..."
    fi
fi

# 6. Check/Wake up Fly.io Machine
echo "🌤️  [6/11] Checking remote machine status..."
MACHINE_ID=$(get_machine_id)
MACHINE_STATUS=$(get_machine_state)

if [ "$MACHINE_STATUS" == "stopped" ] || [ "$MACHINE_STATUS" == "suspended" ]; then
    echo "   💤 Machine is sleeping. Waking it up..."
    curl -s -o /dev/null --max-time 5 "https://$APP_NAME.fly.dev/health" || true
    fly machine start "$MACHINE_ID" > /dev/null 2>&1
    echo "   ✅ Wake-up signal sent. Waiting 10s for boot..."
    sleep 10
else
    echo "   ✅ Machine is running."
fi

disable_autostop_for_deploy "$MACHINE_ID"
trap 'restore_autostop_after_deploy "$MACHINE_ID"; rm -rf "$UPLOAD_WORK_DIR"' EXIT

# 7. Remote Backup
echo "🛡️  [7/11] Creating remote backup on server..."
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

# 8. Upload New DB (Resumable Staged)
echo "🚀 [8/11] Uploading fresh database (compressed staged upload)..."

UPLOAD_WORK_DIR=$(mktemp -d "${TMPDIR:-/tmp}/experts-db-upload.XXXXXX")
LOCAL_GZ_PATH="$UPLOAD_WORK_DIR/experts.db.gz"
LOCAL_CHUNK_PATH="$UPLOAD_WORK_DIR/chunk.bin"

echo "   🗜️  Compressing local DB before upload..."
gzip -c "$DB_PATH" > "$LOCAL_GZ_PATH"

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
        dd if="$LOCAL_GZ_PATH" of="$LOCAL_CHUNK_PATH" bs="$UPLOAD_CHUNK_BYTES" skip="$CHUNK_INDEX" count=1 2>/dev/null
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

# 9. Restart Application
echo "🔄 [9/11] Restarting application to load new DB..."
fly apps restart "$APP_NAME"
echo "   ✅ Restart command sent."

echo "========================================================"
echo "🎉 SUCCESS! Production database updated."
echo "========================================================"
