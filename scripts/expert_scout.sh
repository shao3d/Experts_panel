#!/usr/bin/env bash
# VM-side Expert Scout wrapper: runs the agentic corpus scout and prints
# only the final answer. Intended to be called from the Mac shim or locally.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OPENCODE_BIN="${OPENCODE_BIN:-$HOME/.opencode/bin/opencode}"
PYTHON_BIN="$REPO_DIR/backend/.venv/bin/python"

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
"$OPENCODE_BIN" run --agent expert-scout --variant max --format json "$@" \
  | "$PYTHON_BIN" "$REPO_DIR/scripts/expert_scout_filter.py"
