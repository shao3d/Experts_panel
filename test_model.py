import asyncio
import os
from dotenv import load_dotenv

# Пробуем загрузить основной .env
load_dotenv(dotenv_path=".env")

from openai import AsyncOpenAI

async def test_model():
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("FAILED: No GEMINI_API_KEY found anywhere")
        return

    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    
    try:
        response = await client.chat.completions.create(
            model='gemini-3.1-flash-lite-preview',
            messages=[{"role": "user", "content": "Return the word 'pong'."}],
            max_tokens=10
        )
        print(f"SUCCESS: {response.choices[0].message.content}")
    except Exception as e:
        print(f"FAILED: {e}")

if __name__ == "__main__":
    asyncio.run(test_model())
