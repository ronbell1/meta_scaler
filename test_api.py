"""Quick API connection test."""
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

import os

print("API_BASE_URL:", os.environ.get("API_BASE_URL", "NOT SET"))
print("MODEL_NAME:", os.environ.get("MODEL_NAME", "NOT SET"))
token = os.environ.get("HF_TOKEN", "")
print("HF_TOKEN:", token[:10] + "..." if token else "NOT SET")
print()

print("Testing API connection...")
from openai import OpenAI

client = OpenAI(
    base_url=os.environ["API_BASE_URL"],
    api_key=os.environ["HF_TOKEN"],
    timeout=30.0,
)
try:
    resp = client.chat.completions.create(
        model=os.environ["MODEL_NAME"],
        messages=[{"role": "user", "content": "Say hello in one word."}],
        max_tokens=10,
    )
    print("SUCCESS:", resp.choices[0].message.content)
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
