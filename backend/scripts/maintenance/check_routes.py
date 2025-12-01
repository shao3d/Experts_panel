#!/usr/bin/env python3
"""Check available FastAPI routes."""

import sys
import os
from pathlib import Path

# Set up environment
os.environ['BACKEND_LOG_FILE'] = 'logs/backend.log'
os.environ['FRONTEND_LOG_FILE'] = 'logs/frontend.log'

# Create logs directory
logs_dir = Path(__file__).parent / 'logs'
logs_dir.mkdir(exist_ok=True)

# Import app
sys.path.insert(0, str(Path(__file__).parent))
from src.api.main import app

print("Available routes:")
print("=" * 60)

for route in app.routes:
    if hasattr(route, 'path') and hasattr(route, 'methods'):
        methods = ','.join(route.methods) if route.methods else 'N/A'
        print(f"{methods:10s} {route.path}")

print("=" * 60)

# Check if experts endpoint exists
experts_route = any(
    hasattr(route, 'path') and route.path == '/api/v1/experts'
    for route in app.routes
)

if experts_route:
    print("✅ /api/v1/experts endpoint found!")
else:
    print("❌ /api/v1/experts endpoint NOT found!")
