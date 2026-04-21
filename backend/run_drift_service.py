#!/usr/bin/env python3
"""
CLI Wrapper for DriftSchedulerService.
Runs the full drift analysis cycle on pending comment groups.
"""

import sys
import os
from pathlib import Path

# Add backend root to path so we can import src as a package
sys.path.append(str(Path(__file__).parent))

from src.services.drift_scheduler_service import DriftSchedulerService
from src.models.base import SessionLocal

import asyncio

def main():
    print("🚀 Starting Drift Analysis Service...")
    
    # Ensure we have API keys
    if not (
        os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
        or os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    ):
        print(
            "⚠️  Warning: Vertex AI credentials not set. "
            "Analysis might fail if the service account JSON is unavailable."
        )
    
    db = SessionLocal()
    try:
        scheduler = DriftSchedulerService(db)
        # Run the full cycle asynchronously
        asyncio.run(scheduler.run_full_cycle())
        print("✅ Drift Analysis Cycle Completed Successfully.")
    except Exception as e:
        print(f"❌ Fatal Error in Drift Analysis: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    finally:
        db.close()

if __name__ == "__main__":
    main()
