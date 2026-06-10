"""
examples/anthropic_example.py — Anthropic + TokenLens SDK demo.

Prerequisites:
    pip install tokenlens-sdk[anthropic]
    Set ANTHROPIC_API_KEY and TOKENLENS_API_KEY in your environment.
"""

import os
from anthropic import Anthropic
from tokenlens import TokenLens

TOKENLENS_API_KEY = os.environ["TOKENLENS_API_KEY"]
TOKENLENS_URL     = os.getenv("TOKENLENS_URL", "http://localhost:8000")

tl     = TokenLens(api_key=TOKENLENS_API_KEY, base_url=TOKENLENS_URL, application="anthropic-demo")
client = tl.wrap(Anthropic())

response = client.messages.create(
    model="claude-3-5-haiku-20241022",
    max_tokens=256,
    messages=[{"role": "user", "content": "What is the capital of France?"}],
)
print(response.content[0].text)
# Token usage logged transparently.
