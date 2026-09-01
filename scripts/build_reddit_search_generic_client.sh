#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
PACKAGE_TEMPLATE="$ROOT_DIR/clients/reddit-search-generic"
OUTPUT_DIR="${REDDIT_SEARCH_PACKAGE_OUTPUT_DIR:-$ROOT_DIR/dist}"
PACKAGE_NAME="${REDDIT_SEARCH_PACKAGE_NAME:-reddit-search-generic-client}"
TOKEN_SOURCE="${REDDIT_SEARCH_TOKEN_FILE:-}"
STAGING_DIR="$(mktemp -d "${TMPDIR:-/tmp}/${PACKAGE_NAME}.XXXXXX")"

cleanup() {
  rm -rf "$STAGING_DIR"
}
trap cleanup EXIT

mkdir -p "$STAGING_DIR/$PACKAGE_NAME" "$OUTPUT_DIR"
cp "$PACKAGE_TEMPLATE/install.sh" "$STAGING_DIR/$PACKAGE_NAME/install.sh"
cp "$PACKAGE_TEMPLATE/AGENT_INSTRUCTIONS.md" "$STAGING_DIR/$PACKAGE_NAME/AGENT_INSTRUCTIONS.md"
cp "$PACKAGE_TEMPLATE/AGENT_SETUP.md" "$STAGING_DIR/$PACKAGE_NAME/AGENT_SETUP.md"
cp "$ROOT_DIR/scripts/reddit_search_runner.py" "$STAGING_DIR/$PACKAGE_NAME/reddit_search_runner.py"
chmod 755 "$STAGING_DIR/$PACKAGE_NAME/install.sh"

if [[ -n "$TOKEN_SOURCE" ]]; then
  if [[ ! -f "$TOKEN_SOURCE" || ! -s "$TOKEN_SOURCE" ]]; then
    echo 'REDDIT_SEARCH_TOKEN_FILE must point to a non-empty regular file.' >&2
    exit 1
  fi
  cp "$TOKEN_SOURCE" "$STAGING_DIR/$PACKAGE_NAME/.reddit-search-token"
  chmod 600 "$STAGING_DIR/$PACKAGE_NAME/.reddit-search-token"
fi

archive_path="$OUTPUT_DIR/$PACKAGE_NAME.zip"
rm -f "$archive_path"
python3 - "$STAGING_DIR" "$PACKAGE_NAME" "$archive_path" <<'PY'
from pathlib import Path
import sys
import zipfile

staging = Path(sys.argv[1])
package_name = sys.argv[2]
archive = Path(sys.argv[3])
package_root = staging / package_name

with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
    for path in sorted(package_root.rglob("*")):
        if path.is_file():
            bundle.write(path, path.relative_to(staging))
PY
printf 'Built package: %s\n' "$archive_path"
if [[ -n "$TOKEN_SOURCE" ]]; then
  printf '%s\n' 'Credential included: transfer this personalized archive privately.'
else
  printf '%s\n' 'No credential included: this is a reusable template archive.'
fi
