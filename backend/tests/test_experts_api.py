#!/usr/bin/env python3
"""Integration test for the experts metadata endpoint."""

import json
import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

BACKEND_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{BACKEND_DIR / 'data' / 'experts.db'}")
os.environ.setdefault("BACKEND_LOG_FILE", str(BACKEND_DIR / "logs" / "backend.log"))
os.environ.setdefault("FRONTEND_LOG_FILE", str(BACKEND_DIR / "logs" / "frontend.log"))

from src.api.main import app


def test_experts_api():
    """Test the experts API endpoint via FastAPI TestClient."""

    with TestClient(app) as client:
        health_response = client.get("/health")
        assert health_response.status_code == 200, health_response.text

        response = client.get("/api/v1/experts")
        assert response.status_code == 200, response.text

        experts = response.json()
    assert isinstance(experts, list), f"Expected list, got {type(experts)}"
    assert experts, "No experts returned"

    print(f"✅ Received {len(experts)} experts")
    print("\nExperts data:")
    print(json.dumps(experts, indent=2, ensure_ascii=False))

    required_fields = ["expert_id", "display_name", "channel_username"]
    for expert in experts:
        for field in required_fields:
            assert field in expert, f"Expert missing required field: {field}"
        print(f"  ✅ {expert['expert_id']}: {expert['display_name']} (@{expert['channel_username']})")

    expert_ids = {e["expert_id"] for e in experts}
    expected_experts = {"refat", "ai_architect", "neuraldeep"}

    if expected_experts != expert_ids:
        print("\n⚠️  Expert IDs mismatch:")
        print(f"   Expected: {expected_experts}")
        print(f"   Got: {expert_ids}")
        if expected_experts - expert_ids:
            print(f"   Missing: {expected_experts - expert_ids}")
        if expert_ids - expected_experts:
            print(f"   Extra: {expert_ids - expected_experts}")
    else:
        print("\n✅ All expected experts present")


if __name__ == "__main__":
    test_experts_api()
