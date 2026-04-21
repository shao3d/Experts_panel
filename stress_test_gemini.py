import asyncio
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

# Load backend env and reuse the project's Vertex runtime.
BACKEND_DIR = Path(__file__).parent / "backend"
load_dotenv(BACKEND_DIR / ".env")
sys.path.insert(0, str(BACKEND_DIR))

from src import config
from src.services.google_ai_studio_client import create_google_ai_studio_client

if not (
    os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON")
    or os.getenv("VERTEX_AI_SERVICE_ACCOUNT_JSON_PATH")
    or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
):
    print("❌ No Vertex AI credentials found in backend/.env")
    exit(1)

model_name = os.getenv("STRESS_TEST_MODEL", config.MODEL_ANALYSIS)
client = create_google_ai_studio_client()

async def make_request(i):
    start = time.time()
    try:
        response = await client.chat_completions_create(
            model=model_name,
            messages=[{"role": "user", "content": f"Say 'ok {i}'."}],
            temperature=0.0,
            max_tokens=16,
        )
        duration = time.time() - start
        content = response.choices[0].message.content.strip()
        return f"✅ Req {i}: Success ({duration:.2f}s) - {content}"
    except Exception as e:
        duration = time.time() - start
        return f"❌ Req {i}: Failed ({duration:.2f}s) - {str(e)[:100]}"

async def main():
    print(f"🚀 Starting stress test with 20 parallel requests to {model_name}...")
    tasks = [make_request(i) for i in range(1, 21)]
    results = await asyncio.gather(*tasks)
    
    success_count = len([r for r in results if "✅" in r])
    print("\n--- Results ---")
    for r in results:
        print(r)
    print(f"\nSuccess Rate: {success_count}/20")

if __name__ == "__main__":
    asyncio.run(main())
