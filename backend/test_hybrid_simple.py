#!/usr/bin/env python3
"""Simple test for hybrid LLM functionality.

This script tests the Google AI Studio + OpenRouter hybrid functionality
without importing the full backend modules.
"""

import os
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the current directory to path for imports
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_environment():
    """Test environment configuration."""
    print("🧪 Environment Configuration Test")
    print("=" * 40)

    # Check environment variables
    google_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")
    hybrid_enabled = os.getenv("HYBRID_ENABLED", "true").lower() in ["true", "1", "yes"]

    print(f"GOOGLE_AI_STUDIO_API_KEY: {'✅ Set' if google_key else '❌ Not set'}")
    print(f"OPENROUTER_API_KEY: {'✅ Set' if openrouter_key else '❌ Not set'}")
    print(f"HYBRID_ENABLED: {'✅ True' if hybrid_enabled else '❌ False'}")
    print()

    if google_key:
        print("🎉 Google AI Studio API key is available!")
        print("   The system will try Google AI Studio first, then fallback to OpenRouter")
    elif openrouter_key:
        print("⚠️  Only OpenRouter API key is available")
        print("   The system will use OpenRouter only")
    else:
        print("❌ No API keys configured")
        print("   Please set at least one API key in .env file")

    print()

def test_simple_imports():
    """Test importing our hybrid modules."""
    print("🧪 Import Test")
    print("=" * 40)

    try:
        # Try importing just the google client
        from src.services.google_ai_studio_client import is_google_ai_studio_available
        print("✅ Google AI Studio client imported successfully")
        print(f"   is_google_ai_studio_available(): {is_google_ai_studio_available()}")
    except Exception as e:
        print(f"❌ Failed to import Google AI Studio client: {e}")

    print()

def test_api_key_validation():
    """Test API key validation."""
    print("🧪 API Key Validation Test")
    print("=" * 40)

    google_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY", "")
    openrouter_key = os.getenv("OPENROUTER_API_KEY", "")

    # Test Google AI Studio key format
    if google_key:
        if google_key.startswith("AIzaSy") and len(google_key) == 39:
            print("✅ Google AI Studio API key format looks valid")
        else:
            print("⚠️  Google AI Studio API key format may be invalid")
            print(f"   Expected: AIzaSy... (39 chars), Got: {google_key[:10]}... ({len(google_key)} chars)")
    else:
        print("❌ Google AI Studio API key not provided")

    # Test OpenRouter key format
    if openrouter_key:
        if openrouter_key.startswith("sk-or-v1") and len(openrouter_key) > 40:
            print("✅ OpenRouter API key format looks valid")
        else:
            print("⚠️  OpenRouter API key format may be invalid")
            print(f"   Expected: sk-or-v1..., Got: {openrouter_key[:10]}... ({len(openrouter_key)} chars)")
    else:
        print("❌ OpenRouter API key not provided")

    print()

def main():
    """Run all simple tests."""
    print("🔬 Simple Hybrid LLM Test Suite")
    print("=" * 50)
    print()

    # Test environment
    test_environment()

    # Test imports
    test_simple_imports()

    # Test API key validation
    test_api_key_validation()

    print("💡 Configuration Guide:")
    print("   1. Copy .env.example to .env")
    print("   2. Add your API keys:")
    print("      GOOGLE_AI_STUDIO_API_KEY=AIzaSyCTBfkVB9ilMRlsQY8N4woOMGB7hE2P0EY")
    print("      OPENROUTER_API_KEY=sk-or-v1-your-key-here")
    print("      HYBRID_ENABLED=true")
    print("   3. The system will automatically try Google AI Studio first!")
    print()

    # Check if ready for hybrid mode
    google_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
    openrouter_key = os.getenv("OPENROUTER_API_KEY")

    if google_key and openrouter_key:
        print("🎉 Perfect! Your system is ready for hybrid LLM mode!")
        print("   ✅ Free Google AI Studio usage when available")
        print("   ✅ Automatic fallback to OpenRouter when limits exceeded")
    elif openrouter_key:
        print("✅ Your system is ready with OpenRouter mode!")
        print("   💡 Consider adding Google AI Studio API key for free usage")
    else:
        print("⚠️  Please configure API keys to use the system")

if __name__ == "__main__":
    main()