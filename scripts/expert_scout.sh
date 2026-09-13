#!/usr/bin/env bash
# VM-side Expert Scout wrapper: runs the agentic corpus scout with a hard
# timeout, saves run artifacts (question, raw events, answer, meta) and prints
# only the final answer. Intended to be called from the Mac shim or locally.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCODE_BIN="${OPENCODE_BIN:-$HOME/.opencode/bin/opencode}"
PYTHON_BIN="$REPO_DIR/backend/.venv/bin/python"
TIMEOUT_SECONDS="${EXPERT_SCOUT_TIMEOUT:-300}"
RUNS_DIR="$REPO_DIR/output/scout_runs"

if [[ $# -lt 1 || -z "${1// }" ]]; then
  echo "usage: expert_scout.sh \"<question>\"" >&2
  exit 2
fi

if [[ ! -x "$OPENCODE_BIN" ]]; then
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
OPENCODE_EXIT=0
timeout "$TIMEOUT_SECONDS" \
  "$OPENCODE_BIN" run --agent expert-scout --variant max --format json "$@" \
  > "$RUN_DIR/events.jsonl" || OPENCODE_EXIT=$?
DURATION=$(( $(date +%s) - START_EPOCH ))

TOOL_CALLS="$(grep -c '"type":"tool' "$RUN_DIR/events.jsonl" || true)"

"$PYTHON_BIN" "$REPO_DIR/scripts/expert_scout_filter.py" \
  < "$RUN_DIR/events.jsonl" > "$RUN_DIR/answer.md"

{
  printf 'question: %s\n' "$*"
  printf 'started_epoch: %s\n' "$START_EPOCH"
  printf 'duration_seconds: %s\n' "$DURATION"
  printf 'opencode_exit: %s\n' "$OPENCODE_EXIT"
  printf 'tool_calls: %s\n' "$TOOL_CALLS"
} > "$RUN_DIR/meta.txt"

echo "# scout-run: ${DURATION}s, exit=${OPENCODE_EXIT}, tool_calls=${TOOL_CALLS}, artifacts=${RUN_DIR}" >&2

if [[ -s "$RUN_DIR/answer.md" ]]; then
  cat "$RUN_DIR/answer.md"
elif [[ "$OPENCODE_EXIT" -ne 0 ]]; then
  echo "scout: opencode failed (exit ${OPENCODE_EXIT}); events at ${RUN_DIR}/events.jsonl" >&2
  exit "$OPENCODE_EXIT"
else
  echo "scout: empty answer (agent produced no text); events at ${RUN_DIR}/events.jsonl" >&2
  exit 3
fi
