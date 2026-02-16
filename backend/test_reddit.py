#!/usr/bin/env python3
"""Test Reddit search locally."""

import asyncio
import sys
import os

# Change to backend dir and add src to path
os.chdir('/Users/andreysazonov/Documents/Projects/Experts_panel/backend')
sys.path.insert(0, 'src')

# Test smart targeting function directly
def get_target_subreddits(query: str):
    """Extract relevant subreddits based on query keywords."""
    SUBREDDIT_MAPPING = {
        # AI / LLM
        "llm": ["LocalLLaMA", "OpenAI", "ClaudeAI", "artificial", "MachineLearning"],
        "ai": ["artificial", "MachineLearning", "singularity", "OpenAI"],
        "local": ["LocalLLaMA", "selfhosted", "homelab"],
        
        # Voice / TTS / STT
        "tts": ["tts", "TextToSpeech", "voice", "LocalLLaMA", "HomeAssistantAI"],
        "stt": ["speechRecognition", "voice", "LocalLLaMA", "HomeAssistantAI"],
        "voice": ["voice", "speechRecognition", "tts", "LocalLLaMA"],
        "speech": ["speechRecognition", "voice", "tts"],
        "audio": ["audio", "voice", "musicproduction", "WeAreTheMusicMakers"],
        
        # Programming
        "python": ["Python", "learnpython", "MachineLearning"],
        "javascript": ["javascript", "webdev", "reactjs"],
        "rust": ["rust", "learnrust", "Programming"],
        
        # Hardware
        "gpu": ["LocalLLaMA", "nvidia", "AMD", "hardware"],
        "nvidia": ["nvidia", "LocalLLaMA", "hardware"],
        "amd": ["AMD", "LocalLLaMA", "hardware"],
        
        # Tools / Software
        "docker": ["docker", "selfhosted", "homelab", "sysadmin"],
        "ollama": ["LocalLLaMA", "ollama", "selfhosted"],
        "home assistant": ["HomeAssistantAI", "homeautomation", "smarthome"],
        "automation": ["automation", "HomeAssistantAI", "selfhosted"],
        
        # General tech
        "self-hosted": ["selfhosted", "homelab", "LocalLLaMA"],
        "selfhosted": ["selfhosted", "homelab", "LocalLLaMA"],
        "privacy": ["privacy", "selfhosted", "degoogle", "privacytoolsIO"],
        
        # Default fallback
        "default": ["LocalLLaMA", "OpenAI", "artificial", "technology"],
    }
    
    query_lower = query.lower()
    matched_subreddits = set()
    
    for keyword, subreddits in SUBREDDIT_MAPPING.items():
        if keyword in query_lower:
            matched_subreddits.update(subreddits)
    
    if matched_subreddits:
        return list(matched_subreddits)[:5]
    return SUBREDDIT_MAPPING["default"]


def test_smart_targeting():
    """Test smart subreddit targeting."""
    print("=" * 70)
    print("🎯 Testing Smart Subreddit Targeting")
    print("=" * 70)
    
    test_queries = [
        ("Какие сейчас есть удобные движки TTS и STT?", "Russian TTS/STT query"),
        ("best TTS engines 2024", "English TTS query"),
        ("local LLM models ollama", "Local LLM query"),
        ("voice recognition tools", "Voice query"),
        ("Python docker setup", "Python/DevOps query"),
        ("random query about cats", "Unrelated query (fallback)"),
    ]
    
    for query, description in test_queries:
        subreddits = get_target_subreddits(query)
        print(f"\n📌 {description}")
        print(f"   Query: '{query[:50]}...'")
        print(f"   → Target subreddits: {subreddits}")


def test_query_translation():
    """Simulate Gemini query translation."""
    print("\n" + "=" * 70)
    print("🤖 Simulating Gemini Query Translation")
    print("=" * 70)
    
    # This simulates what Gemini would produce
    translations = [
        ("Какие сейчас есть удобные движки TTS и STT?", "TTS STT engines 2024"),
        ("Лучшие локальные LLM для дома", "local LLM selfhosted"),
        ("Как убрать галлюцинации в LLM?", "LLM hallucination fix"),
    ]
    
    for original, translated in translations:
        subreddits_original = get_target_subreddits(original)
        subreddits_translated = get_target_subreddits(translated)
        
        print(f"\n📝 Original (RU): '{original[:40]}...'")
        print(f"   → Subreddits: {subreddits_original}")
        print(f"🌐 Translated (EN): '{translated}'")
        print(f"   → Subreddits: {subreddits_translated}")


if __name__ == "__main__":
    test_smart_targeting()
    test_query_translation()
    
    print("\n" + "=" * 70)
    print("✅ Smart targeting test complete!")
    print("=" * 70)
