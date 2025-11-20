#!/usr/bin/env python3
"""
Test script for expert metadata API endpoint.
Starts backend, tests /api/v1/experts endpoint, and stops backend.
"""

import subprocess
import time
import sys
import requests
import json
from pathlib import Path

def test_experts_api():
    """Test the experts API endpoint."""
    backend_process = None

    try:
        # Step 1: Start backend
        print("🚀 Starting backend server...")

        # Set up environment for development
        import os
        env = os.environ.copy()
        env['BACKEND_LOG_FILE'] = 'logs/backend.log'
        env['FRONTEND_LOG_FILE'] = 'logs/frontend.log'

        # Create logs directory if it doesn't exist
        logs_dir = Path(__file__).parent / 'logs'
        logs_dir.mkdir(exist_ok=True)

        backend_process = subprocess.Popen(
            ["python3", "-m", "uvicorn", "src.api.main:app", "--host", "127.0.0.1", "--port", "8000"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=Path(__file__).parent,
            env=env,
            text=True
        )

        # Wait for server to start
        print("⏳ Waiting for server to start...")
        max_retries = 20
        for i in range(max_retries):
            try:
                response = requests.get("http://localhost:8000/health", timeout=1)
                if response.status_code == 200:
                    print(f"✅ Backend started (attempt {i+1}/{max_retries})")
                    break
            except requests.exceptions.RequestException:
                time.sleep(0.5)
        else:
            print("❌ Backend failed to start within 10 seconds")
            return False

        # Give backend extra time to fully initialize
        print("⏳ Waiting for backend to fully initialize...")
        time.sleep(2)

        # Step 2: Test /api/v1/experts endpoint
        print("\n📡 Testing /api/v1/experts endpoint...")
        try:
            response = requests.get("http://localhost:8000/api/v1/experts", timeout=5)

            if response.status_code != 200:
                print(f"❌ Unexpected status code: {response.status_code}")
                print(f"Response: {response.text}")
                return False

            experts = response.json()

            # Validate response structure
            if not isinstance(experts, list):
                print(f"❌ Expected list, got {type(experts)}")
                return False

            if len(experts) == 0:
                print("❌ No experts returned")
                return False

            print(f"✅ Received {len(experts)} experts")
            print("\nExperts data:")
            print(json.dumps(experts, indent=2, ensure_ascii=False))

            # Validate each expert has required fields
            required_fields = ['expert_id', 'display_name', 'channel_username']
            for expert in experts:
                for field in required_fields:
                    if field not in expert:
                        print(f"❌ Expert missing required field: {field}")
                        return False
                print(f"  ✅ {expert['expert_id']}: {expert['display_name']} (@{expert['channel_username']})")

            # Check for expected experts
            expert_ids = {e['expert_id'] for e in experts}
            expected_experts = {'refat', 'ai_architect', 'neuraldeep'}

            if expected_experts != expert_ids:
                print(f"\n⚠️  Expert IDs mismatch:")
                print(f"   Expected: {expected_experts}")
                print(f"   Got: {expert_ids}")
                if expected_experts - expert_ids:
                    print(f"   Missing: {expected_experts - expert_ids}")
                if expert_ids - expected_experts:
                    print(f"   Extra: {expert_ids - expected_experts}")
            else:
                print(f"\n✅ All expected experts present")

            print("\n🎉 All tests passed!")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ Request failed: {e}")
            return False
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON response: {e}")
            return False

    except Exception as e:
        print(f"❌ Test failed with exception: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Step 3: Stop backend
        if backend_process:
            print("\n🛑 Stopping backend server...")
            backend_process.terminate()
            try:
                backend_process.wait(timeout=5)
                print("✅ Backend stopped cleanly")
            except subprocess.TimeoutExpired:
                backend_process.kill()
                print("⚠️  Backend killed forcefully")


if __name__ == '__main__':
    success = test_experts_api()
    sys.exit(0 if success else 1)
