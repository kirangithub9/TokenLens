"""
examples/openai_example.py — OpenAI + TokenLens SDK demo.

Prerequisites:
    pip install tokenlens-sdk[openai]
    Set OPENAI_API_KEY and TOKENLENS_API_KEY in your environment.
"""

import os
from openai import OpenAI
from tokenlens import TokenLens

TOKENLENS_API_KEY = os.environ["TOKENLENS_API_KEY"]   # tl-...
TOKENLENS_URL     = os.getenv("TOKENLENS_URL", "http://localhost:8000")

# 1. Create and wrap the OpenAI client — one extra line, then use it normally.
tl     = TokenLens(api_key=TOKENLENS_API_KEY, base_url=TOKENLENS_URL, application="openai-demo")
client = tl.wrap(OpenAI())

# 2. Call the API exactly as you would without TokenLens.
response = client.chat.completions.create(
    model="gpt-4o-mini",
    messages=[{"role": "user", "content": "Explain quantum entanglement in two sentences."}],
)
print(response.choices[0].message.content)
# TokenLens silently logged tokens, latency, and cost in the background.

# ── Manual logging ────────────────────────────────────────────────────────────
# Use tl.log() if you are calling LLMs through a custom client or framework.

tl.log(
    model="gpt-4o-mini",
    tokens_in=150,
    tokens_out=42,
    latency_ms=830.5,
    query_text="Manually logged request",
)
print("Manual log sent.")
