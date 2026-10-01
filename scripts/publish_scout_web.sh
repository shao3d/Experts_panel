#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ -n "$(git status --porcelain -- scout-web)" ]]; then
    echo 'Commit scout-web changes before publication.' >&2
    exit 1
fi
revision=$(git subtree split --prefix=scout-web HEAD)
git push https://github.com/shao3d/scout-web.git "$revision:main"
