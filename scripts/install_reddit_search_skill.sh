#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
SKILL_DIR="$CODEX_HOME/skills/reddit-search"
BIN_DIR="${REDDIT_SEARCH_BIN_DIR:-$HOME/.local/bin}"

mkdir -p "$SKILL_DIR/agents" "$BIN_DIR"
cp "$ROOT_DIR/.codex/skills/reddit-search/SKILL.md" "$SKILL_DIR/SKILL.md"
cp "$ROOT_DIR/.codex/skills/reddit-search/agents/openai.yaml" "$SKILL_DIR/agents/openai.yaml"
cp "$ROOT_DIR/scripts/reddit_search_runner.py" "$SKILL_DIR/reddit_search_runner.py"
chmod 700 "$SKILL_DIR/reddit_search_runner.py"

cat > "$BIN_DIR/reddit-search" <<EOF
#!/usr/bin/env bash
set -euo pipefail
exec python3 "$SKILL_DIR/reddit_search_runner.py" "\$@"
EOF
chmod 755 "$BIN_DIR/reddit-search"

printf 'Installed global Codex skill: %s\n' "$SKILL_DIR"
printf 'Installed command: %s/reddit-search\n' "$BIN_DIR"
printf '%s\n' 'Set AGENT_CONTEXT_API_TOKEN in your user environment before searching.'
printf '%s\n' 'No token was created, copied, or printed by this installer.'
