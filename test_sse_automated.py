#!/usr/bin/env python3
"""
Automated SSE Integration Test
Tests the SSE streaming endpoint without manual interaction
"""

import json
import time
import requests
import sseclient
import sys
from typing import List, Dict

def test_sse_streaming():
    """Test SSE streaming with a sample query"""

    print("🧪 Automated SSE Integration Test")
    print("=" * 50)

    # Check backend health first
    try:
        health_response = requests.get("http://localhost:8000/health")
        health_data = health_response.json()
        print(f"✅ Backend health: {health_data['status']}")

        if not health_data.get('openai_configured'):
            print("❌ ERROR: OpenAI API key not configured!")
            print("Please set OPENAI_API_KEY in backend/.env")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ ERROR: Backend not running!")
        print("Start it with: cd backend && uvicorn src.api.main:app --reload")
        return False

    # Test query
    test_query = "What are the key technical decisions in this project?"
    print(f"\n📝 Test query: '{test_query}'")
    print("-" * 50)

    # Setup SSE connection
    url = f"http://localhost:8000/api/v1/query/stream?query={test_query}"

    events_received: List[Dict] = []
    phases_completed = set()

    try:
        print("\n🔄 Connecting to SSE endpoint...")
        response = requests.get(url, stream=True)
        client = sseclient.SSEClient(response)

        print("📡 Receiving events:\n")

        for event in client.events():
            if event.data:
                try:
                    data = json.loads(event.data)
                    events_received.append(data)

                    # Display event
                    event_type = data.get('type', 'unknown')
                    phase = data.get('phase', '')
                    message = data.get('message', '')

                    if event_type == 'phase_start':
                        print(f"  ▶️  Starting {phase} phase: {message}")
                    elif event_type == 'map_progress':
                        chunk = data.get('chunk', 0)
                        total = data.get('total', 0)
                        posts = data.get('posts_in_chunk', 0)
                        print(f"  📊 Map progress: chunk {chunk}/{total} ({posts} posts)")
                    elif event_type == 'phase_complete':
                        phases_completed.add(phase)
                        print(f"  ✅ Completed {phase} phase")
                    elif event_type == 'result':
                        print(f"  🎯 Got final result!")
                        if data.get('result'):
                            result = data['result']
                            print(f"\n📋 Result Summary:")
                            print(f"  - Sources found: {len(result.get('sources', []))}")
                            print(f"  - Answer length: {len(result.get('answer', ''))} chars")
                            stats = result.get('processing_stats', {})
                            print(f"  - Posts analyzed: {stats.get('total_posts_analyzed', 0)}")
                            print(f"  - Processing time: {stats.get('processing_time_seconds', 0):.2f}s")
                        break
                    elif event_type == 'error':
                        print(f"  ❌ Error: {data.get('error', 'Unknown error')}")
                        return False

                except json.JSONDecodeError as e:
                    print(f"  ⚠️  Failed to parse event: {e}")

    except KeyboardInterrupt:
        print("\n\n🛑 Test interrupted by user")
        return False
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        return False

    # Validate results
    print("\n" + "=" * 50)
    print("📊 Test Results:")
    print(f"  - Total events received: {len(events_received)}")
    print(f"  - Phases completed: {', '.join(phases_completed)}")

    success = True

    # Check if all phases completed
    expected_phases = {'map', 'resolve', 'reduce'}
    if phases_completed != expected_phases:
        print(f"  ❌ Missing phases: {expected_phases - phases_completed}")
        success = False
    else:
        print(f"  ✅ All phases completed successfully")

    # Check if we got a result
    result_events = [e for e in events_received if e.get('type') == 'result']
    if not result_events:
        print(f"  ❌ No result received")
        success = False
    else:
        print(f"  ✅ Final result received")

    if success:
        print("\n✅ SSE Integration Test PASSED!")
    else:
        print("\n❌ SSE Integration Test FAILED!")

    return success


if __name__ == "__main__":
    # Install sseclient-py if not available
    try:
        import sseclient
    except ImportError:
        print("Installing sseclient-py...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "sseclient-py"])
        import sseclient

    success = test_sse_streaming()
    sys.exit(0 if success else 1)