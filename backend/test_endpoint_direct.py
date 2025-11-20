#!/usr/bin/env python3
"""Direct test of experts endpoint without starting server."""

import sys
import os
from pathlib import Path

# Set up environment
os.environ['BACKEND_LOG_FILE'] = 'logs/backend.log'
os.environ['FRONTEND_LOG_FILE'] = 'logs/frontend.log'

# Create logs directory
logs_dir = Path(__file__).parent / 'logs'
logs_dir.mkdir(exist_ok=True)

# Import FastAPI test client
from fastapi.testclient import TestClient

# Import app
sys.path.insert(0, str(Path(__file__).parent))
from src.api.main import app

# Create test client
client = TestClient(app)

print("🧪 Testing /api/v1/experts endpoint directly...")
print()

# Test the endpoint
response = client.get("/api/v1/experts")

print(f"Status Code: {response.status_code}")
print(f"Response: {response.text}")
print()

if response.status_code == 200:
    import json
    data = response.json()
    print(f"✅ Success! Received {len(data)} experts:")
    print(json.dumps(data, indent=2, ensure_ascii=False))
else:
    print(f"❌ Failed with status {response.status_code}")
