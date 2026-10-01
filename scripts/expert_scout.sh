#!/usr/bin/env bash
# VM-side Expert Scout wrapper: runs the agentic corpus scout with a hard
# timeout, saves run artifacts (question, raw events, answer, meta) and prints
# only the final answer. Intended to be called from the Mac shim or locally.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCODE_BIN="${OPENCODE_BIN:-$HOME/.opencode/bin/opencode}"
SCOUT_ENGINE="${EXPERT_SCOUT_ENGINE:-sol}"
CODEX_BIN="${CODEX_BIN:-$(command -v codex || true)}"
PYTHON_BIN="$REPO_DIR/backend/.venv/bin/python"
TIMEOUT_SECONDS="${EXPERT_SCOUT_TIMEOUT:-900}"
RUNS_DIR="$REPO_DIR/output/scout_runs"

if [[ $# -lt 1 || -z "${1// }" ]]; then
  echo "usage: expert_scout.sh \"<question>\"" >&2
  exit 2
fi

if [[ "$SCOUT_ENGINE" != sol && "$SCOUT_ENGINE" != bunny ]]; then
  echo "Error: EXPERT_SCOUT_ENGINE must be sol or bunny" >&2
  exit 2
fi
if [[ "$SCOUT_ENGINE" == sol && ! -x "$CODEX_BIN" ]]; then
  echo "Error: codex not found" >&2
  exit 1
fi
if [[ "$SCOUT_ENGINE" == bunny && ! -x "$OPENCODE_BIN" ]]; then
  echo "Error: opencode not found at $OPENCODE_BIN" >&2
  exit 1
fi
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: backend python not found at $PYTHON_BIN" >&2
  exit 1
fi

cd "$REPO_DIR"

STAMP="$(date +%Y%m%d-%H%M%S)-$$"
RUN_DIR="$RUNS_DIR/$STAMP"
mkdir -p "$RUN_DIR"
printf '%s\n' "$*" > "$RUN_DIR/question.txt"

START_EPOCH="$(date +%s)"
ENGINE_EXIT=0
if [[ "$SCOUT_ENGINE" == sol ]]; then
  export CODEX_BIN
  ENGINE_COMMAND=("$PYTHON_BIN" "$REPO_DIR/scripts/expert_scout_codex.py")
else
  ENGINE_COMMAND=("$OPENCODE_BIN" run --agent expert-scout --variant max --format json)
fi
timeout "$TIMEOUT_SECONDS" "${ENGINE_COMMAND[@]}" "$@" \
  > "$RUN_DIR/events.jsonl" || ENGINE_EXIT=$?
DURATION=$(( $(date +%s) - START_EPOCH ))

TOOL_CALLS="$("$PYTHON_BIN" -c 'import json,sys; from pathlib import Path; sys.path.insert(0,str(Path.cwd()/"backend")); from src.utils.scout_evidence import tool_calls; print(len(tool_calls([json.loads(line) for line in sys.stdin if line.strip()])))' < "$RUN_DIR/events.jsonl")"

FILTER_EXIT=0
"$PYTHON_BIN" "$REPO_DIR/scripts/expert_scout_filter.py" \
  < "$RUN_DIR/events.jsonl" > "$RUN_DIR/answer.md" || FILTER_EXIT=$?

# Deterministic integrity check: cited keys must exist, quotes must be real,
# repeated tool calls are flagged (docs/guides/expert-scout.md).
if [[ "${SCOUT_WEB_PROGRESS:-0}" == 1 ]]; then
  echo 'SCOUT_PROGRESS "Проверяю ответ и источники…"' >&2
fi
set +e
"$PYTHON_BIN" "$REPO_DIR/backend/scripts/verify_citations.py" \
  --answer "$RUN_DIR/answer.md" --events "$RUN_DIR/events.jsonl" \
  --json --annotate > "$RUN_DIR/integrity.json" 2> "$RUN_DIR/integrity.log"
INTEGRITY_EXIT=$?
set -e
INTEGRITY_SUMMARY="$(tail -n 1 "$RUN_DIR/integrity.log" 2>/dev/null || true)"

{
  printf 'question: %s\n' "$*"
  printf 'started_epoch: %s\n' "$START_EPOCH"
  printf 'duration_seconds: %s\n' "$DURATION"
  printf 'engine_exit: %s\n' "$ENGINE_EXIT"
  printf 'engine: %s\n' "$SCOUT_ENGINE"
  if [[ "$SCOUT_ENGINE" == sol ]]; then
    printf 'model: gpt-6.1-sol\nreasoning: low\nservice_tier_requested: fast\n'
  fi
  printf 'tool_calls: %s\n' "$TOOL_CALLS"
  printf 'integrity_exit: %s\n' "$INTEGRITY_EXIT"
  printf 'filter_exit: %s\n' "$FILTER_EXIT"
  printf 'integrity: %s\n' "$INTEGRITY_SUMMARY"
} > "$RUN_DIR/meta.txt"

STATUS=completed
if [[ "$ENGINE_EXIT" -ne 0 ]]; then STATUS=error
elif [[ "$FILTER_EXIT" -ne 0 || "$INTEGRITY_EXIT" -ne 0 ]]; then STATUS=partial
fi
echo "# scout-run: ${DURATION}s, engine=${SCOUT_ENGINE}, exit=${ENGINE_EXIT}, tool_calls=${TOOL_CALLS}, integrity_exit=${INTEGRITY_EXIT}, status=${STATUS} ${INTEGRITY_SUMMARY}, artifacts=${RUN_DIR}" >&2

if [[ -s "$RUN_DIR/answer.md" ]]; then
  if [[ "$ENGINE_EXIT" -ne 0 ]]; then
    printf '# WARNING: scout engine failed (exit %s); this answer is partial.\n\n' "$ENGINE_EXIT"
  fi
  cat "$RUN_DIR/answer.md"
  if [[ "$ENGINE_EXIT" -ne 0 ]]; then exit "$ENGINE_EXIT"; fi
  if [[ "$FILTER_EXIT" -ne 0 ]]; then exit "$FILTER_EXIT"; fi
  if [[ "$INTEGRITY_EXIT" -ne 0 ]]; then exit 4; fi
elif [[ "$ENGINE_EXIT" -ne 0 ]]; then
  echo "scout: engine failed (exit ${ENGINE_EXIT}); events at ${RUN_DIR}/events.jsonl" >&2
  exit "$ENGINE_EXIT"
else
  echo "scout: empty answer (agent produced no text); events at ${RUN_DIR}/events.jsonl" >&2
  exit 3
fi
