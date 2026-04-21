import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Reuse the backend Vertex runtime instead of the legacy Gemini API key path.
BACKEND_DIR = Path(__file__).parent / "backend"
load_dotenv(BACKEND_DIR / ".env")
sys.path.insert(0, str(BACKEND_DIR))

from src import config
from src.services.google_ai_studio_client import create_google_ai_studio_client

async def test_model():
    if not (
        os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
        or os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH")
        or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    ):
        print("FAILED: No Vertex AI credentials found in backend/.env")
        return

    client = create_google_ai_studio_client()
    model = os.getenv("TEST_MODEL", config.MODEL_SCOUT)
    
    try:
        response = await client.chat_completions_create(
            model=model,
            messages=[{"role": "user", "content": "Return the word 'pong'."}],
            temperature=0.0,
            max_tokens=10,
        )
        print(f"SUCCESS: {response.choices[0].message.content}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_model())
