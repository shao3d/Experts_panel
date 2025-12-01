#!/usr/bin/env python3
"""Test script for hybrid LLM functionality.

This script tests the Google AI Studio + OpenRouter hybrid functionality
by simulating API calls and verifying fallback behavior.
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Add backend src to path
backend_src = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(backend_src))

from services.hybrid_llm_adapter import create_hybrid_client, is_hybrid_mode_enabled
from services.hybrid_llm_monitor import get_monitor, log_api_call_with_timing
from services.google_ai_studio_client import GoogleAIStudioError

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def test_hybrid_client():
    """Test the hybrid LLM client functionality."""

    print("🧪 Testing Hybrid LLM Client")
    print("=" * 50)

    # Check environment
    print("🔧 Environment Check:")
    print(f"   HYBRID_ENABLED: {os.getenv('HYBRID_ENABLED', 'not set')}")
    print(f"   GOOGLE_AI_STUDIO_API_KEY: {'set' if os.getenv('GOOGLE_AI_STUDIO_API_KEY') else 'not set'}")
    print(f"   OPENROUTER_API_KEY: {'set' if os.getenv('OPENROUTER_API_KEY') else 'not set'}")
    print(f"   Hybrid mode enabled: {is_hybrid_mode_enabled()}")
    print()

    # Create hybrid client
    try:
        client = create_hybrid_client(
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            google_ai_studio_api_key=os.getenv("GOOGLE_AI_STUDIO_API_KEY"),
            enable_hybrid=True
        )

        status = client.get_status()
        print("✅ Hybrid client created successfully:")
        for key, value in status.items():
            print(f"   {key}: {value}")
        print()

    except Exception as e:
        print(f"❌ Failed to create hybrid client: {e}")
        return

    # Test API call
    print("🚀 Testing API Call:")
    test_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'Hello from hybrid LLM!' in JSON format: {\"response\": \"your_message\"}"}
    ]

    try:
        response = await client.chat_completions_create(
            model="gemini-2.0-flash",
            messages=test_messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            service_name="test"
        )

        print("✅ API call successful!")
        print(f"   Response: {response.choices[0].message.content}")
        print(f"   Usage: {response.usage}")

    except Exception as e:
        print(f"❌ API call failed: {e}")

    print()

    # Show monitoring stats
    print("📊 Monitoring Statistics:")
    monitor = get_monitor()
    monitor.log_summary()
    stats = monitor.get_stats()

    print(f"   Detailed stats: {stats}")
    print()


async def test_error_handling():
    """Test error handling and fallback scenarios."""

    print("🧪 Testing Error Handling")
    print("=" * 50)

    # Create client with invalid Google AI Studio key to force fallback
    client = create_hybrid_client(
        openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
        google_ai_studio_api_key="invalid-key-to-force-fallback",
        enable_hybrid=True
    )

    print("🔄 Testing with invalid Google AI Studio key (should fallback to OpenRouter)...")

    test_messages = [
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say 'Fallback test successful!' in JSON format: {\"test\": \"success\"}"}
    ]

    try:
        response = await client.chat_completions_create(
            model="gemini-2.0-flash",
            messages=test_messages,
            temperature=0.1,
            response_format={"type": "json_object"},
            service_name="fallback_test"
        )

        print("✅ Fallback successful!")
        print(f"   Response: {response.choices[0].message.content}")

    except Exception as e:
        print(f"❌ Even fallback failed: {e}")

    print()

    # Monitor fallback stats
    monitor = get_monitor()
    monitor.log_summary()


def test_manual_monitoring():
    """Test manual monitoring functionality."""

    print("🧪 Testing Manual Monitoring")
    print("=" * 50)

    import time

    # Simulate some API calls
    monitor = get_monitor()
    monitor.reset()

    # Simulate Google AI Studio success
    monitor.record_api_call(
        service_name="test",
        provider="google_ai_studio",
        model="gemini-2.0-flash",
        success=True,
        response_time_ms=1250,
        token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        is_fallback=False
    )

    # Simulate Google AI Studio rate limit
    monitor.record_api_call(
        service_name="test",
        provider="google_ai_studio",
        model="gemini-2.0-flash",
        success=False,
        error_type="rate_limit",
        error_message="Resource has been exhausted",
        is_fallback=False
    )

    # Simulate OpenRouter fallback success
    monitor.record_api_call(
        service_name="test",
        provider="openrouter",
        model="google/gemini-2.0-flash-001",
        success=True,
        response_time_ms=890,
        token_usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
        is_fallback=True
    )

    print("📊 Manual monitoring test complete:")
    monitor.log_summary()


async def main():
    """Run all tests."""
    print("🔬 Hybrid LLM Test Suite")
    print("=" * 60)
    print()

    # Test basic functionality
    await test_hybrid_client()

    # Test error handling
    await test_error_handling()

    # Test manual monitoring
    test_manual_monitoring()

    print("🎉 All tests completed!")
    print()
    print("💡 Tips:")
    print("   - Set GOOGLE_AI_STUDIO_API_KEY in .env to test Google AI Studio")
    print("   - Set OPENROUTER_API_KEY in .env for fallback testing")
    print("   - Set HYBRID_ENABLED=true to enable hybrid mode")
    print("   - Monitor logs to see provider switching in action")


if __name__ == "__main__":
    asyncio.run(main())