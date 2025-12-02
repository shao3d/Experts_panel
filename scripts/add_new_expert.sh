#!/bin/bash

# ==============================================================================
# Script: add_new_expert.sh
# Purpose: Automate the entire process of adding a new expert
# Usage: ./scripts/add_new_expert.sh <expert_id> "<Display Name>" <username> <json_path>
# ==============================================================================

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check arguments
if [ "$#" -ne 4 ]; then
    echo -e "${RED}Usage: $0 <expert_id> \"<Display Name>\" <username> <json_path>${NC}"
    echo "Example: $0 neuraldeep \"Neuraldeep\" neuraldeep exports/neuraldeep.json"
    exit 1
fi

EXPERT_ID=$1
DISPLAY_NAME=$2
USERNAME=$3
JSON_PATH=$4

# Ensure we are in project root
if [ ! -f "fly.toml" ]; then
    echo -e "${RED}❌ Error: Please run this script from the project root directory.${NC}"
    exit 1
fi

# Load environment variables from backend/.env if it exists
# CRITICAL: Needed for Telegram API credentials in Step 2
if [ -f "backend/.env" ]; then
    echo "🔑 Loading environment variables from backend/.env..."
    set -a
    source backend/.env
    set +a
else
    echo -e "${YELLOW}⚠️ Warning: backend/.env not found. Telegram Sync might fail if env vars are not set.${NC}"
fi

# Set Environment Variables for Scripts
export DATABASE_URL="sqlite:///backend/data/experts.db"
export PYTHONPATH=$PYTHONPATH:$(pwd)/backend

echo -e "${GREEN}🚀 STARTING NEW EXPERT REGISTRATION PROCESS${NC}"
echo "--------------------------------------------------------"
echo "Expert ID:    $EXPERT_ID"
echo "Name:         $DISPLAY_NAME"
echo "Username:     $USERNAME"
echo "JSON File:    $JSON_PATH"
echo "--------------------------------------------------------"

# 1. Register Expert (Metadata + Posts + Sync State)
echo -e "\n${YELLOW}📝 Step 1: Registering expert and importing posts...${NC}"
# add_expert.py now automatically initializes sync_state
python3 backend/tools/add_expert.py "$EXPERT_ID" "$DISPLAY_NAME" "$USERNAME" "$JSON_PATH"

# 2. Sync Comments & Prepare Drift Analysis
echo -e "\n${YELLOW}💬 Step 2: Fetching ALL comments for the new expert...${NC}"
echo "This might take a while depending on the number of posts."
echo "Using depth=2000 to ensure we cover everything."
echo "Also automatically creates 'pending' drift analysis records."

# We pass TELEGRAM_CHANNEL explicitly as required by sync_channel.py
# We use '|| true' to prevent the script from stopping if sync encounters a minor error (like a single post failure)
TELEGRAM_CHANNEL="$USERNAME" python3 backend/sync_channel.py --expert-id "$EXPERT_ID" --depth 2000 || true

echo -e "\n${GREEN}✅ Expert registration and initial sync complete!${NC}"
echo "--------------------------------------------------------"

# 3. Prompt for Production Deploy
echo -e "\n${YELLOW}🚀 Ready to deploy to production?${NC}"
echo "This will run Drift Analysis (Gemini) on all new comments (~15s per post)."
read -p "Do you want to run 'update_production_db.sh' now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ./scripts/update_production_db.sh
else
    echo -e "\n${GREEN}OK, you can run it later manually:${NC}"
    echo "./scripts/update_production_db.sh"
fi
