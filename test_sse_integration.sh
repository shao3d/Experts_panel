#!/bin/bash

# SSE Integration Test Script
echo "🚀 Starting SSE Integration Test..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if OPENAI_API_KEY is set
if ! grep -q "OPENAI_API_KEY=sk-" backend/.env; then
    echo -e "${RED}❌ ERROR: Please set your OPENAI_API_KEY in backend/.env${NC}"
    echo "Edit backend/.env and replace 'your_openai_api_key_here' with your actual key"
    exit 1
fi

# Function to kill processes on exit
cleanup() {
    echo -e "\n${YELLOW}🛑 Stopping servers...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit
}

trap cleanup EXIT INT TERM

# Start backend
echo -e "${GREEN}▶️  Starting backend server...${NC}"
cd backend
python -m uvicorn src.api.main:app --reload --port 8000 &
BACKEND_PID=$!
cd ..

# Wait for backend to start
echo "Waiting for backend to start..."
sleep 5

# Check backend health
echo -e "${GREEN}🔍 Checking backend health...${NC}"
curl -s http://localhost:8000/health | python -m json.tool

# Start frontend
echo -e "${GREEN}▶️  Starting frontend server...${NC}"
cd frontend
npm run dev &
FRONTEND_PID=$!
cd ..

# Wait for frontend to start
echo "Waiting for frontend to start..."
sleep 5

echo -e "${GREEN}✅ Both servers are running!${NC}"
echo ""
echo "📋 Test Instructions:"
echo "1. Open http://localhost:5173 in your browser"
echo "2. Enter a test query like: 'What are the main topics discussed?'"
echo "3. Watch the SSE progress updates in real-time"
echo "4. Verify that you see:"
echo "   - Map phase progress (chunk by chunk)"
echo "   - Resolve phase progress"
echo "   - Reduce phase progress"
echo "   - Final result with sources"
echo ""
echo "Press Ctrl+C to stop the servers when done testing"

# Keep script running
wait