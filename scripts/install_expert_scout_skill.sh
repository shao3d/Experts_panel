#!/usr/bin/env bash
# Install the Expert Scout skill for Codex and opencode.
#
# Usage:
#   scripts/install_expert_scout_skill.sh            # install skills only
#   scripts/install_expert_scout_skill.sh --with-shim # + Mac shim (~/.local/bin/expert-scout)
#
# The shim is intended for a Mac that reaches the VM by SSH; skip it on the VM.
set -euo pipefail

ROOT_DIR="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)"
SKILL_SRC="$ROOT_DIR/.codex/skills/expert-scout"
CODEX_HOME="${CODEX_HOME:-$HOME/.codex}"
OPENCODE_SKILLS_DIR="${OPENCODE_SKILLS_DIR:-$HOME/.config/opencode/skills}"
INSTALL_SHIM=0

if [[ "${1:-}" == "--with-shim" ]]; then
  INSTALL_SHIM=1
fi

for required in "$SKILL_SRC/SKILL.md" "$SKILL_SRC/agents/openai.yaml"; do
  if [[ ! -f "$required" ]]; then
    echo "Error: missing $required" >&2
    exit 1
  fi
done

mkdir -p "$CODEX_HOME/skills/expert-scout/agents"
cp "$SKILL_SRC/SKILL.md" "$CODEX_HOME/skills/expert-scout/SKILL.md"
cp "$SKILL_SRC/agents/openai.yaml" "$CODEX_HOME/skills/expert-scout/agents/openai.yaml"
printf 'Installed Codex skill: %s\n' "$CODEX_HOME/skills/expert-scout"

mkdir -p "$OPENCODE_SKILLS_DIR/expert-scout"
cp "$SKILL_SRC/SKILL.md" "$OPENCODE_SKILLS_DIR/expert-scout/SKILL.md"
printf 'Installed opencode skill: %s\n' "$OPENCODE_SKILLS_DIR/expert-scout"

if [[ "$INSTALL_SHIM" == "1" ]]; then
  BIN_DIR="${EXPERT_SCOUT_BIN_DIR:-$HOME/.local/bin}"
  mkdir -p "$BIN_DIR"
  cat > "$BIN_DIR/expert-scout" <<'SHIM'
#!/usr/bin/env bash
# Expert Scout bridge (Mac): sends the question to the VM-side agentic scout.
set -euo pipefail

if [[ $# -lt 1 || -z "${1// }" ]]; then
  echo "usage: expert-scout \"<question>\"" >&2
  exit 2
fi

REMOTE="${EXPERT_SCOUT_REMOTE:-ubuntu@82.70.251.73}"
REPO="${EXPERT_SCOUT_REPO:-/home/ubuntu/apps/experts-panel/dev}"

Q=$(printf '%s' "$*" | base64 | tr -d '\n')

exec ssh -o BatchMode=yes -o ConnectTimeout=10 \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=10 \
  "$REMOTE" \
  "cd '$REPO' && EXPERT_SCOUT_TIMEOUT='${EXPERT_SCOUT_TIMEOUT:-300}' ./scripts/expert_scout.sh \"\$(printf '%s' '$Q' | base64 -d)\""
SHIM
  chmod 755 "$BIN_DIR/expert-scout"
  printf 'Installed command: %s/expert-scout\n' "$BIN_DIR"
fi

printf '%s\n' 'Scout is read-only and runs on the VM; no token or secret is created, copied, or printed.'
