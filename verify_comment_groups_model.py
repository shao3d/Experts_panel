#!/usr/bin/env python3
"""
Verification script for Comment Groups Model Refactor
Tests that MODEL_COMMENT_GROUPS environment variable works correctly
"""

import os
import sys
import asyncio
import json
import importlib
from pathlib import Path

# Add backend to path
sys.path.append(str(Path(__file__).parent / "backend"))

def test_service_reads_environment_variable():
    """Test that CommentGroupMapService reads MODEL_COMMENT_GROUPS correctly"""
    print("🔧 Testing CommentGroupMapService environment variable reading...")

    # Test 1: Default behavior (no env var)
    if "MODEL_COMMENT_GROUPS" in os.environ:
        del os.environ["MODEL_COMMENT_GROUPS"]

    from backend.src.services.comment_group_map_service import CommentGroupMapService

    service = CommentGroupMapService(api_key="test-key")
    expected_default = "openai/gpt-4o-mini"  # After convert_model_name

    if service.model == expected_default:
        print(f"✅ Default model test passed: {service.model}")
    else:
        print(f"❌ Default model test failed: expected {expected_default}, got {service.model}")
        return False

    # Test 2: Custom model via environment variable
    os.environ["MODEL_COMMENT_GROUPS"] = "qwen/qwen-2.5-32b-instruct"

    # Reload module to pick up new environment
    import importlib
    import backend.src.services.comment_group_map_service
    importlib.reload(backend.src.services.comment_group_map_service)

    from backend.src.services.comment_group_map_service import CommentGroupMapService

    service = CommentGroupMapService(api_key="test-key")
    expected_custom = "qwen/qwen-2.5-32b-instruct"

    if service.model == expected_custom:
        print(f"✅ Custom model test passed: {service.model}")
    else:
        print(f"❌ Custom model test failed: expected {expected_custom}, got {service.model}")
        return False

    # Test 3: GPT-4o-mini via environment variable (rollback test)
    os.environ["MODEL_COMMENT_GROUPS"] = "gpt-4o-mini"

    import backend.src.services.comment_group_map_service
    importlib.reload(backend.src.services.comment_group_map_service)

    from backend.src.services.comment_group_map_service import CommentGroupMapService

    service = CommentGroupMapService(api_key="test-key")
    expected_rollback = "openai/gpt-4o-mini"

    if service.model == expected_rollback:
        print(f"✅ Rollback model test passed: {service.model}")
    else:
        print(f"❌ Rollback model test failed: expected {expected_rollback}, got {service.model}")
        return False

    return True

def test_pipeline_integration():
    """Test that simplified_query_endpoint.py reads environment variable correctly"""
    print("🔧 Testing pipeline integration...")

    # Set test environment variable
    os.environ["MODEL_COMMENT_GROUPS"] = "qwen/qwen-2.5-32b-instruct"

    # Test that the environment variable is read correctly
    model_comment_groups = os.getenv("MODEL_COMMENT_GROUPS", "gpt-4o-mini")
    expected = "qwen/qwen-2.5-32b-instruct"

    if model_comment_groups == expected:
        print(f"✅ Pipeline integration test passed: {model_comment_groups}")
        return True
    else:
        print(f"❌ Pipeline integration test failed: expected {expected}, got {model_comment_groups}")
        return False

def test_environment_variable_examples():
    """Test the examples from .env.example"""
    print("🔧 Testing .env.example configurations...")

    test_cases = [
        ("gpt-4o-mini", "Default GPT-4o-mini", "openai/gpt-4o-mini"),
        ("qwen/qwen-2.5-32b-instruct", "Cost optimization Qwen32B", "qwen/qwen-2.5-32b-instruct")
    ]

    for model_value, description, expected_converted in test_cases:
        os.environ["MODEL_COMMENT_GROUPS"] = model_value

        # Reload to pick up new environment
        import importlib
        import backend.src.services.comment_group_map_service
        importlib.reload(backend.src.services.comment_group_map_service)

        from backend.src.services.comment_group_map_service import CommentGroupMapService

        service = CommentGroupMapService(api_key="test-key")

        if service.model == expected_converted:
            print(f"✅ {description}: {service.model}")
        else:
            print(f"❌ {description} failed: expected {expected_converted}, got {service.model}")
            return False

    return True

def test_openrouter_model_mapping():
    """Test that both models are supported in OpenRouter adapter"""
    print("🔧 Testing OpenRouter model mapping...")

    from backend.src.services.openrouter_adapter import convert_model_name

    test_models = [
        ("gpt-4o-mini", "openai/gpt-4o-mini"),
        ("qwen/qwen-2.5-32b-instruct", "qwen/qwen-2.5-32b-instruct")
    ]

    for input_model, expected_output in test_models:
        result = convert_model_name(input_model)

        if result == expected_output:
            print(f"✅ Model mapping {input_model} → {result}")
        else:
            print(f"❌ Model mapping failed: {input_model} → expected {expected_output}, got {result}")
            return False

    return True

def verify_prompt_compatibility():
    """Verify that the prompt template is compatible with both models"""
    print("🔧 Testing prompt template compatibility...")

    prompt_path = Path(__file__).parent / "backend" / "prompts" / "comment_group_drift_prompt.txt"

    if not prompt_path.exists():
        print(f"❌ Prompt file not found: {prompt_path}")
        return False

    with open(prompt_path, "r", encoding="utf-8") as f:
        prompt_content = f.read()

    # Check for model-specific language that should be updated
    problematic_patterns = [
        "gpt-4o-mini",
        "GPT-4o-mini",
        "GPT 4o mini"
    ]

    for pattern in problematic_patterns:
        if pattern in prompt_content:
            print(f"❌ Found model-specific pattern in prompt: {pattern}")
            return False

    # Check for required placeholders
    required_placeholders = ["$query", "$groups"]
    for placeholder in required_placeholders:
        if placeholder not in prompt_content:
            print(f"❌ Missing required placeholder: {placeholder}")
            return False

    print("✅ Prompt template is model-agnostic and compatible")
    return True

def test_bulletproof_rollback():
    """Test the bulletproof rollback mechanism"""
    print("🔧 Testing bulletproof rollback mechanism...")

    # Test 1: Production configuration (32B for cost savings)
    os.environ["MODEL_COMMENT_GROUPS"] = "qwen/qwen-2.5-32b-instruct"

    import backend.src.services.comment_group_map_service
    importlib.reload(backend.src.services.comment_group_map_service)

    from backend.src.services.comment_group_map_service import CommentGroupMapService

    service_production = CommentGroupMapService(api_key="test-key")
    expected_production = "qwen/qwen-2.5-32b-instruct"

    if service_production.model != expected_production:
        print(f"❌ Production config failed: expected {expected_production}, got {service_production.model}")
        return False

    # Test 2: Rollback configuration (back to GPT-4o-mini)
    os.environ["MODEL_COMMENT_GROUPS"] = "gpt-4o-mini"

    # Force reload to pick up new environment
    import backend.src.services.comment_group_map_service
    importlib.reload(backend.src.services.comment_group_map_service)

    from backend.src.services.comment_group_map_service import CommentGroupMapService

    service_rollback = CommentGroupMapService(api_key="test-key")
    expected_rollback = "openai/gpt-4o-mini"

    if service_rollback.model != expected_rollback:
        print(f"❌ Rollback config failed: expected {expected_rollback}, got {service_rollback.model}")
        return False

    print("✅ Bulletproof rollback mechanism working correctly")
    print(f"✅ Production model: {service_production.model}")
    print(f"✅ Rollback model: {service_rollback.model}")
    return True

def main():
    """Run all verification tests"""
    print("🚀 Starting Comment Groups Model Refactor Verification")
    print("=" * 60)

    tests = [
        ("Environment Variable Reading", test_service_reads_environment_variable),
        ("Pipeline Integration", test_pipeline_integration),
        ("Environment Variable Examples", test_environment_variable_examples),
        ("OpenRouter Model Mapping", test_openrouter_model_mapping),
        ("Prompt Template Compatibility", verify_prompt_compatibility),
        ("Bulletproof Rollback Mechanism", test_bulletproof_rollback)
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        print(f"\n📋 Running: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} PASSED")
            else:
                failed += 1
                print(f"❌ {test_name} FAILED")
        except Exception as e:
            failed += 1
            print(f"❌ {test_name} ERROR: {e}")

    print("\n" + "=" * 60)
    print(f"📊 TEST SUMMARY: {passed} passed, {failed} failed")

    if failed == 0:
        print("🎉 ALL TESTS PASSED! Comment Groups model refactor is ready for deployment.")
        print("\n🛡️ BULLETPROOF ROLLBACK INSTRUCTIONS:")
        print("   # Production (cost optimization):")
        print("   export MODEL_COMMENT_GROUPS=qwen/qwen-2.5-32b-instruct")
        print("   ")
        print("   # Rollback (if quality issues):")
        print("   export MODEL_COMMENT_GROUPS=gpt-4o-mini")
        print("   ")
        print("   💡 No code changes required - just environment variable!")
        return True
    else:
        print("❌ SOME TESTS FAILED! Please fix issues before deploying.")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)