#!/bin/bash
set -e
REPO_DIR=$(mktemp -d)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Cloning pixel-agents..."
git clone --depth 1 https://github.com/pablodelucca/pixel-agents "$REPO_DIR"

ASSETS_SRC="$REPO_DIR/webview-ui/public/assets"
ASSETS_DST="$PROJECT_DIR/frontend/public/pixel-office"

mkdir -p "$ASSETS_DST"/{characters,floors,walls,furniture}

cp "$ASSETS_SRC"/characters/char_*.png "$ASSETS_DST/characters/"
cp "$ASSETS_SRC"/floors/floor_*.png "$ASSETS_DST/floors/"
cp "$ASSETS_SRC"/walls/wall_0.png "$ASSETS_DST/walls/"
cp -r "$ASSETS_SRC"/furniture/* "$ASSETS_DST/furniture/"
cp "$ASSETS_SRC"/default-layout-1.json "$ASSETS_DST/"

# Generate furniture index (browser cannot readdir on /public/)
# Use node instead of jq — guaranteed available in a frontend project
node -e "
  const fs = require('fs');
  const dirs = fs.readdirSync('$ASSETS_DST/furniture')
    .filter(f => fs.statSync('$ASSETS_DST/furniture/' + f).isDirectory());
  fs.writeFileSync('$ASSETS_DST/furniture-index.json', JSON.stringify(dirs, null, 2));
  console.log('Generated furniture-index.json with', dirs.length, 'entries');
"

rm -rf "$REPO_DIR"
echo "Done. Assets copied to frontend/public/pixel-office/"
