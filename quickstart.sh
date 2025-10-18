#!/bin/bash

# Experts Panel - Quick Start Script
# This script helps you quickly set up and start the project

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Print header
echo -e "${BOLD}${BLUE}"
echo "============================================"
echo "   Experts Panel - Quick Start Setup"
echo "============================================"
echo -e "${NC}"

# Function to check command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Step 1: Check basic requirements
echo -e "${BOLD}Step 1: Checking basic requirements...${NC}"

if ! command_exists python3; then
    echo -e "${RED}❌ Python3 not found. Please install Python 3.11+${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Python3 found"

if ! command_exists node; then
    echo -e "${RED}❌ Node.js not found. Please install Node.js 18+${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} Node.js found"

if ! command_exists npm; then
    echo -e "${RED}❌ npm not found. Please install npm${NC}"
    exit 1
fi
echo -e "${GREEN}✓${NC} npm found"

# Step 2: Set up backend
echo -e "\n${BOLD}Step 2: Setting up backend...${NC}"

cd backend

# Install Python dependencies
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python dependencies..."
pip install -q -r requirements.txt
echo -e "${GREEN}✓${NC} Backend dependencies installed"

# Create .env if it doesn't exist
if [ ! -f ".env" ]; then
    if [ -f ".env.example" ]; then
        cp .env.example .env
        echo -e "${YELLOW}⚠${NC} Created .env from .env.example"
        echo -e "${YELLOW}   Please edit backend/.env and add your OPENAI_API_KEY${NC}"
    else
        echo -e "${YELLOW}⚠${NC} Creating default .env file"
        cat > .env << EOF
# Backend environment variables
OPENAI_API_KEY=your_openai_api_key_here
DATABASE_URL=sqlite:///data/experts.db
ENVIRONMENT=development
LOG_LEVEL=INFO
EOF
        echo -e "${YELLOW}   Please edit backend/.env and add your OPENAI_API_KEY${NC}"
    fi
else
    echo -e "${GREEN}✓${NC} .env file exists"
fi

cd ..

# Step 3: Set up frontend
echo -e "\n${BOLD}Step 3: Setting up frontend...${NC}"

cd frontend

if [ ! -d "node_modules" ]; then
    echo "Installing frontend dependencies..."
    npm install --silent
    echo -e "${GREEN}✓${NC} Frontend dependencies installed"
else
    echo -e "${GREEN}✓${NC} Frontend dependencies already installed"
fi

cd ..

# Step 4: Set up database
echo -e "\n${BOLD}Step 4: Setting up database...${NC}"

if [ ! -d "data" ]; then
    mkdir -p data
    echo -e "${GREEN}✓${NC} Created data directory"
fi

if [ ! -f "data/experts.db" ]; then
    echo -e "${YELLOW}⚠${NC} Database not found. Creating empty database..."

    # Create database with schema
    python3 << EOF
import sqlite3
from pathlib import Path

db_path = Path("data/experts.db")
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables
cursor.execute('''
CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    telegram_message_id INTEGER UNIQUE NOT NULL,
    author TEXT NOT NULL,
    content TEXT NOT NULL,
    date TIMESTAMP NOT NULL,
    reply_to_message_id INTEGER,
    forward_from TEXT,
    views INTEGER DEFAULT 0,
    reactions TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_post_id INTEGER NOT NULL,
    target_post_id INTEGER NOT NULL,
    link_type TEXT NOT NULL,
    context TEXT,
    FOREIGN KEY (source_post_id) REFERENCES posts(telegram_message_id),
    FOREIGN KEY (target_post_id) REFERENCES posts(telegram_message_id),
    UNIQUE(source_post_id, target_post_id, link_type)
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS expert_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expert_name TEXT NOT NULL,
    comment_text TEXT NOT NULL,
    related_post_ids TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
''')

conn.commit()
conn.close()

print("Database created successfully!")
EOF

    echo -e "${GREEN}✓${NC} Database created"
    echo -e "${YELLOW}   To import Telegram data:${NC}"
    echo -e "${YELLOW}   1. Place JSON export in data/exports/${NC}"
    echo -e "${YELLOW}   2. Run: cd backend && python -m src.data.json_parser <json_file>${NC}"
else
    echo -e "${GREEN}✓${NC} Database exists"
fi

# Step 5: Validation
echo -e "\n${BOLD}Step 5: Running validation...${NC}"

if [ -f "quickstart_validate.py" ]; then
    echo "Running validation script..."
    python3 quickstart_validate.py
else
    echo -e "${YELLOW}⚠${NC} Validation script not found, skipping..."
fi

# Step 6: Show how to start
echo -e "\n${BOLD}${GREEN}✅ Setup Complete!${NC}"
echo ""
echo -e "${BOLD}To start the application:${NC}"
echo ""
echo "1. Start Backend (in one terminal):"
echo "   cd backend"
echo "   source venv/bin/activate"
echo "   uvicorn src.api.main:app --reload --port 8000"
echo ""
echo "2. Start Frontend (in another terminal):"
echo "   cd frontend"
echo "   npm run dev"
echo ""
echo "3. Open your browser:"
echo "   http://localhost:5173"
echo ""
echo -e "${YELLOW}Remember to set your OPENAI_API_KEY in backend/.env!${NC}"
echo ""
echo -e "${GREEN}Happy coding! 🚀${NC}"