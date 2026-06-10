"""
examples/async_example.py — Async OpenAI + TokenLens SDK demo.

Prerequisites:
    pip install tokenlens-sdk[openai]
"""

import asyncio
import os
from openai import AsyncOpenAI
from tokenlens import TokenLens

TOKENLENS_API_KEY = os.environ["TOKENLENS_API_KEY"]
TOKENLENS_URL     = os.getenv("TOKENLENS_URL", "http://localhost:8000")


async def main():
    tl     = TokenLens(api_key=TOKENLENS_API_KEY, base_url=TOKENLENS_URL, application="async-demo")
    client = tl.wrap(AsyncOpenAI())

    response = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Name three planets in our solar system."}],
    )
    print(response.choices[0].message.content)

    # Async manual log — awaits the HTTP call, returns the response dict.
    result = await tl.alog(
        model="gpt-4o-mini",
        tokens_in=80,
        tokens_out=25,
        latency_ms=450.0,
        query_text="Name three planets in our solar system.",
    )
    print(f"Logged: usage_id={result['usage_id']}  cost_usd={result['cost_usd']:.8f}")


asyncio.run(main())
