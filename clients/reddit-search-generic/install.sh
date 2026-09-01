#!/usr/bin/env bash
set -euo pipefail

PACKAGE_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
INSTALL_ROOT="${REDDIT_SEARCH_INSTALL_ROOT:-$HOME/.local/share/reddit-search}"
BIN_DIR="${REDDIT_SEARCH_BIN_DIR:-$HOME/.local/bin}"
CONFIG_DIR="${REDDIT_SEARCH_CONFIG_DIR:-$HOME/.config/reddit-search}"
TOKEN_FILE="$CONFIG_DIR/token"
BUNDLED_TOKEN_FILE="$PACKAGE_DIR/.reddit-search-token"
NON_INTERACTIVE=false
VERIFY=false

usage() {
  cat <<'EOF'
Usage: bash install.sh [--non-interactive] [--verify]

  --non-interactive  Never prompt; fail if no bundled, environment, or existing token exists.
  --verify           Run reddit-search --doctor after installation.
EOF
}

for arg in "$@"; do
  case "$arg" in
    --non-interactive) NON_INTERACTIVE=true ;;
    --verify) VERIFY=true ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage >&2; exit 2 ;;
  esac
done

mkdir -p "$INSTALL_ROOT" "$BIN_DIR" "$CONFIG_DIR"
cp "$PACKAGE_DIR/reddit_search_runner.py" "$INSTALL_ROOT/reddit_search_runner.py"
cp "$PACKAGE_DIR/AGENT_INSTRUCTIONS.md" "$CONFIG_DIR/AGENT_INSTRUCTIONS.md"
chmod 700 "$INSTALL_ROOT/reddit_search_runner.py"

if [[ -s "$BUNDLED_TOKEN_FILE" ]]; then
  cp "$BUNDLED_TOKEN_FILE" "$TOKEN_FILE"
elif [[ ! -s "$TOKEN_FILE" ]]; then
  if [[ -n "${REDDIT_SEARCH_API_TOKEN:-}" ]]; then
    printf '%s' "$REDDIT_SEARCH_API_TOKEN" > "$TOKEN_FILE"
  elif [[ "$NON_INTERACTIVE" == false && -t 0 ]]; then
    printf 'Reddit Search client token: ' >&2
    IFS= read -r -s client_token
    printf '\n' >&2
    if [[ -z "$client_token" ]]; then
      echo 'Token is required.' >&2
      exit 1
    fi
    printf '%s' "$client_token" > "$TOKEN_FILE"
    unset client_token
  else
    echo 'No client token found in package, environment, or existing configuration.' >&2
    exit 1
  fi
fi
chmod 600 "$TOKEN_FILE"

# The extracted copy is no longer needed. The original personalized ZIP remains
# a credential and must still be stored and transferred privately.
if [[ -f "$BUNDLED_TOKEN_FILE" ]]; then
  rm -f "$BUNDLED_TOKEN_FILE"
fi

cat > "$BIN_DIR/reddit-search" <<EOF
#!/usr/bin/env bash
set -euo pipefail
token_file="$TOKEN_FILE"
if [[ ! -s "\$token_file" ]]; then
  echo 'Reddit Search token is not configured.' >&2
  exit 1
fi
REDDIT_SEARCH_API_TOKEN="\$(<"\$token_file")"
export REDDIT_SEARCH_API_TOKEN
exec python3 "$INSTALL_ROOT/reddit_search_runner.py" "\$@"
EOF
chmod 755 "$BIN_DIR/reddit-search"

printf 'Installed command: %s/reddit-search\n' "$BIN_DIR"
printf 'Agent instructions: %s/AGENT_INSTRUCTIONS.md\n' "$CONFIG_DIR"
printf '%s\n' 'The token was stored locally with mode 0600 and was not printed.'

if [[ "$VERIFY" == true ]]; then
  "$BIN_DIR/reddit-search" --doctor
fi
