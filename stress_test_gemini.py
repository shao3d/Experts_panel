import asyncio
import os
import time
import google.generativeai as genai
from dotenv import load_dotenv

# Load env vars from backend/.env
load_dotenv("backend/.env")

api_key = os.getenv("GOOGLE_AI_STUDIO_API_KEY")
if not api_key:
    print("❌ No API key found in backend/.env")
    exit(1)

genai.configure(api_key=api_key)
model_name = "gemini-2.0-flash" # Use fast model for stress test

async def make_request(i):
    start = time.time()
    try:
        model = genai.GenerativeModel(model_name)
        response = await model.generate_content_async(f"Say 'ok {i}'")
        duration = time.time() - start
        return f"✅ Req {i}: Success ({duration:.2f}s)"
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
