#!/usr/bin/env bash
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$REPO_ROOT/backend"
PYTHON_BIN="$BACKEND_DIR/.venv/bin/python"
INSTALL_DIR="${PANEX_INSTALL_DIR:-$HOME/.local/bin}"
TARGET="$INSTALL_DIR/panex"

if [[ "${1:-}" == "--print-target" ]]; then
  printf '%s\n' "$TARGET"
  exit 0
fi

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Error: expected executable backend venv python at $PYTHON_BIN" >&2
  echo "Create or repair the backend virtualenv before installing panex." >&2
  exit 1
fi

mkdir -p "$INSTALL_DIR"

cat > "$TARGET" <<SHIM
#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="$PYTHON_BIN"
BACKEND_DIR="$BACKEND_DIR"

if [[ ! -x "\$PYTHON_BIN" ]]; then
  echo "Error: Panex backend python is missing at \$PYTHON_BIN" >&2
  echo "Re-run scripts/install_panex_runner.sh from the Experts_panel repo." >&2
  exit 1
fi

cd "\$BACKEND_DIR"
exec "\$PYTHON_BIN" -m src.cli.panex "\$@"
SHIM

chmod 755 "$TARGET"

echo "Installed panex runner: $TARGET"
echo "Target backend: $BACKEND_DIR"
if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
  echo "Warning: $INSTALL_DIR is not on PATH in this shell." >&2
fi
