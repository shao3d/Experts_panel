"""
Standalone test script for MapService with Gemini provider.

This script initializes MapService with a Gemini model and processes a small,
hardcoded set of posts to verify the integration.

Prerequisites:
- A .env file in the project root with GOOGLE_AI_STUDIO_API_KEY set.
- `pip install -r backend/requirements.txt`
- `pip install python-dotenv` (if not already in requirements)

Usage:
Run from the project root directory:
$ python test_gemini_map.py
"""

import asyncio
import os
import sys
import logging
from datetime import datetime, timedelta
import json

# Ensure the backend directory is in the Python path for module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), 'backend')))

try:
    from dotenv import load_dotenv
    from src.services.map_service import MapService
    from src.models.post import Post
except ImportError as e:
    print(f"Error importing modules: {e}")
    print("Please ensure you have installed dependencies from backend/requirements.txt and are running from the project root.")
    print("You might also need to install python-dotenv: pip install python-dotenv")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables from .env file in the project root
load_dotenv()


async def main():
    """
    Main asynchronous function to run the MapService Gemini integration test.
    """
    logging.info("--- Starting MapService Gemini Integration Test ---")

    # 1. Configuration
    # The script expects GOOGLE_AI_STUDIO_API_KEY to be in your .env file.
    model_name = "gemini/gemini-1.5-flash-latest"
    # api_key is for OpenRouter, not used by Gemini, but required by constructor.
    api_key = os.getenv("OPENROUTER_API_KEY", "dummy_key_for_openrouter")

    if not os.getenv("GOOGLE_AI_STUDIO_API_KEY"):
        logging.error("FATAL: GOOGLE_AI_STUDIO_API_KEY environment variable not set.")
        logging.error("Please add it to your .env file in the project root.")
        return

    # 2. Create mock data
    logging.info("Creating mock post data...")
    mock_posts = [
        Post(
            telegram_message_id=1,
            message_text="The new AI regulations will have a huge impact on startups.",
            author_name="AI Analyst",
            created_at=datetime.now() - timedelta(days=5),
            channel_id=123,
            channel_name="AI News",
            views=1000,
        ),
        Post(
            telegram_message_id=2,
            message_text="I'm looking for a good Italian restaurant in the city center.",
            author_name="Foodie",
            created_at=datetime.now() - timedelta(days=2),
            channel_id=123,
            channel_name="AI News",
            views=50,
        ),
        Post(
            telegram_message_id=3,
            message_text="Self-driving cars are becoming more and more advanced, with new features being rolled out.",
            author_name="Tech Enthusiast",
            created_at=datetime.now() - timedelta(days=1),
            channel_id=123,
            channel_name="AI News",
            views=500,
        ),
        Post(
            telegram_message_id=4,
            message_text="The government just announced new policies on artificial intelligence.",
            author_name="Policy Watcher",
            created_at=datetime.now(),
            channel_id=123,
            channel_name="AI News",
            views=2000,
        ),
    ]

    query = "What is the latest news about AI policy and regulations?"

    # 3. Initialize MapService
    logging.info(f"Initializing MapService with model: {model_name}")
    try:
        map_service = MapService(
            api_key=api_key,
            model=model_name,
            chunk_size=2  # Use a small chunk size for testing
        )
    except ValueError as e:
        logging.error(f"Failed to initialize MapService: {e}")
        return

    # 4. Define a progress callback (optional)
    async def progress_callback(update: dict):
        logging.info(f"Progress update: {json.dumps(update)}")

    # 5. Run the process
    logging.info(f"Processing {len(mock_posts)} posts with query: '{query}'")
    try:
        result = await map_service.process(
            posts=mock_posts,
            query=query,
            expert_id="test_gemini_expert",
            progress_callback=progress_callback
        )

        # 6. Print and validate results
        logging.info("--- Map Phase Completed ---")
        print(json.dumps(result, indent=2, ensure_ascii=False))
        logging.info("---------------------------")

        if result and 'total_processed' in result:
            assert result['total_processed'] == len(mock_posts)
            assert 'relevant_posts' in result
            logging.info(f"Found {len(result['relevant_posts'])} relevant posts.")
            for post in result['relevant_posts']:
                assert 'relevance' in post
                assert 'summary' in post
            logging.info("Result structure looks correct.")
            logging.info("✅ Test script finished successfully.")
        else:
            logging.error("❌ Test failed: The result object is empty or invalid.")

    except Exception as e:
        logging.error(f"An error occurred during processing: {e}", exc_info=True)
        logging.error("❌ Test failed due to an exception.")


if __name__ == "__main__":
    # This script should be run from the root directory of the project
    # so that path adjustments and .env loading work correctly.
    asyncio.run(main())