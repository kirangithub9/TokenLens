# TokenLens SDK

Python SDK for [TokenLens](https://github.com/alumnx-ai-labs/TokenLens) — automatic token counting, latency tracking, and cost calculation for every AI request your application makes.

---

## Table of Contents

- [What It Does](#what-it-does)
- [Installation](#installation)
- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Usage Modes](#usage-modes)
  - [Mode 1 — tl.chat() — Backend as LLM](#mode-1--tlchat----backend-as-llm)
  - [Mode 2 — tl.openai() / tl.anthropic() — Wrap Your Own Client](#mode-2--tlopenai--tlanthropic----wrap-your-own-client)
  - [Mode 3 — tl.log() — Manual Logging](#mode-3--tllog----manual-logging)
- [TokenLens Constructor](#tokenlens-constructor)
- [Method Reference](#method-reference)
- [Response Object](#response-object)
- [Async Support](#async-support)
- [Cost Utilities](#cost-utilities)
- [Supported Models & Pricing](#supported-models--pricing)
- [Error Handling](#error-handling)
- [Where Data Is Saved](#where-data-is-saved)
- [How test_tokenlens.py Works](#how-test_tokenslenspy-works)
- [File Structure](#file-structure)

---

## What It Does

- Tracks **tokens in**, **tokens out**, **latency**, and **cost** for every LLM call
- Saves everything to your TokenLens backend database
- Works with OpenAI, Anthropic, and the TokenLens backend's own models
- Zero changes to your existing LLM code — just wrap the client
- No provider API key needed when routing through your TokenLens backend

---

## Installation

```bash
# Install from local repo (development)
pip install -e /path/to/TokenLens/sdk

# Install with OpenAI support
pip install tokenlens-sdk[openai]

# Install with Anthropic support
pip install tokenlens-sdk[anthropic]

# Install with all provider support
pip install tokenlens-sdk[all]
```

**Requires Python 3.9+**

---

## Prerequisites

Before using the SDK you need:

1. **A running TokenLens backend** — default at `http://localhost:8000`
2. **A TokenLens API key** — generate one from the TokenLens dashboard under **Settings → API Keys**. It looks like `tl-abc123...`

That is all. No OpenAI or Anthropic key is needed in your app when using `tl.chat()`.

---

## Quick Start

```python
from tokenlens import TokenLens

# 1. Create the client
tl = TokenLens(
    api_key  = "tl-your-key-here",
    base_url = "http://localhost:8000",
)

# 2. Get a chat client — routes through your backend, no provider key needed
client = tl.chat()

# 3. Make an LLM call — identical to the OpenAI SDK interface
response = client.chat.completions.create(
    model    = "gpt4o-mini",
    messages = [{"role": "user", "content": "What is the capital of France?"}],
)

# 4. Use the response
print(response.choices[0].message.content)
# → Paris is the capital of France.

print(f"Tokens : {response.usage.total_tokens}")
print(f"Cost   : ${response.cost.usd:.8f}  /  ₹{response.cost.inr:.6f}")
print(f"Latency: {response.latency_ms:.1f} ms")
```

---

## Usage Modes

### Mode 1 — `tl.chat()` — Backend as LLM

Routes every LLM call through your **TokenLens backend**. The backend makes the actual call to OpenAI/Ollama using keys configured in its own `.env`. Your application only needs the `tl-` key.

```python
tl     = TokenLens(api_key="tl-...", base_url="http://localhost:8000")
client = tl.chat()   # starts a new conversation session

response = client.chat.completions.create(
    model    = "gpt4o-mini",     # model must exist in backend config
    messages = [{"role": "user", "content": "Explain async/await in Python."}],
)

print(response.choices[0].message.content)
print(response.cost.usd)      # cost computed by backend
print(response.latency_ms)    # end-to-end latency in ms
```

**Multi-turn conversations** — pass the same `session_id` to maintain memory:

```python
client = tl.chat(session_id="my-session-abc")

# Turn 1
r1 = client.chat.completions.create(
    model    = "gpt4o-mini",
    messages = [{"role": "user", "content": "My name is Sandeep."}],
)

# Turn 2 — backend remembers "Sandeep" from turn 1
r2 = client.chat.completions.create(
    model    = "gpt4o-mini",
    messages = [{"role": "user", "content": "What is my name?"}],
)
print(r2.choices[0].message.content)  # → Your name is Sandeep.
```

**Available models** — depends on your backend configuration:

| Model string | Provider |
|---|---|
| `"gemma"` | Ollama (local) |
| `"gpt4"` | OpenAI GPT-4 |
| `"gpt4o-mini"` | OpenAI GPT-4o Mini |

---

### Mode 2 — `tl.openai()` / `tl.anthropic()` — Wrap Your Own Client

Use this when you already have a provider API key and want TokenLens to log every call automatically. The LLM call goes **directly** to OpenAI/Anthropic — TokenLens only logs the token counts after the fact.

#### OpenAI

```bash
pip install tokenlens-sdk[openai]
```

```python
# Requires OPENAI_API_KEY set in environment
client = tl.openai()

response = client.chat.completions.create(
    model    = "gpt-4o-mini",
    messages = [{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)
# TokenLens silently logged tokens + cost in a background thread
```

**Custom OpenAI settings** (Azure, proxy, org):

```python
client = tl.openai(
    api_key  = "sk-...",
    base_url = "https://your-azure-endpoint.openai.azure.com/",
)
```

#### Anthropic

```bash
pip install tokenlens-sdk[anthropic]
```

```python
# Requires ANTHROPIC_API_KEY set in environment
claude = tl.anthropic()

response = claude.messages.create(
    model     = "claude-3-5-haiku-20241022",
    max_tokens= 512,
    messages  = [{"role": "user", "content": "Hello!"}],
)
print(response.content[0].text)
```

#### Bring Your Own Client — `tl.wrap()`

If you already have a configured client instance:

```python
from openai import OpenAI

my_client = OpenAI(api_key="sk-...", organization="org-...")
client    = tl.wrap(my_client)   # same as tl.openai() but uses your existing instance
```

Supported types for `tl.wrap()`:

- `openai.OpenAI`
- `openai.AsyncOpenAI`
- `anthropic.Anthropic`
- `anthropic.AsyncAnthropic`

---

### Mode 3 — `tl.log()` — Manual Logging

Use when you already have token counts from any source — LangChain, LlamaIndex, a custom HTTP client, or any other framework.

```python
tl.log(
    model      = "gpt-4o-mini",
    tokens_in  = 150,
    tokens_out = 42,
    latency_ms = 830.5,
    query_text = "Summarise this document...",  # optional — shown in dashboard
)
```

By default this is **fire-and-forget** (runs in background thread, returns `None`).

To block and get the response:

```python
tl = TokenLens(api_key="tl-...", background=False)

result = tl.log(
    model      = "gpt-4o-mini",
    tokens_in  = 150,
    tokens_out = 42,
    latency_ms = 830.5,
)
print(result)
# {"usage_id": "uuid...", "cost_usd": 0.00002745, "cost_inr": 0.00233325}
```

---

## TokenLens Constructor

```python
TokenLens(
    api_key        : str,
    base_url       : str   = "http://localhost:8000",
    application    : str   = "tokenlens-sdk",
    background     : bool  = True,
    timeout        : float = 10.0,
    raise_on_error : bool  = False,
)
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `api_key` | `str` | required | Your `tl-` API key from the TokenLens dashboard |
| `base_url` | `str` | `"http://localhost:8000"` | Base URL of your TokenLens backend |
| `application` | `str` | `"tokenlens-sdk"` | Label shown in the dashboard for all log entries from this client |
| `background` | `bool` | `True` | `True` = fire-and-forget (non-blocking). `False` = block and return log result |
| `timeout` | `float` | `10.0` | HTTP timeout in seconds for log requests |
| `raise_on_error` | `bool` | `False` | `False` = log a warning on failure, never crash your app. `True` = raise `LoggingError` |

---

## Method Reference

### `tl.chat(session_id=None)`

Returns a `TokenLensChatClient`. Routes LLM calls through the TokenLens backend.

```python
client = tl.chat()
client = tl.chat(session_id="existing-session-id")  # continue a session
```

### `tl.async_chat(session_id=None)`

Async version. Returns `AsyncTokenLensChatClient`. Use with `await`.

### `tl.openai(**kwargs)`

Creates and wraps an `openai.OpenAI` client. All kwargs forwarded to `OpenAI()`.

```python
client = tl.openai()
client = tl.openai(api_key="sk-...", base_url="https://azure-endpoint/")
```

### `tl.async_openai(**kwargs)`

Creates and wraps an `openai.AsyncOpenAI` client.

### `tl.anthropic(**kwargs)`

Creates and wraps an `anthropic.Anthropic` client.

### `tl.async_anthropic(**kwargs)`

Creates and wraps an `anthropic.AsyncAnthropic` client.

### `tl.wrap(client)`

Wrap an existing provider client instance.

```python
from openai import OpenAI
client = tl.wrap(OpenAI())
```

### `tl.log(*, model, tokens_in, tokens_out, latency_ms, query_text=None, application=None)`

Manually log one AI request.

| Argument | Type | Required | Description |
|---|---|---|---|
| `model` | `str` | yes | Model identifier e.g. `"gpt-4o-mini"` |
| `tokens_in` | `int` | yes | Input / prompt token count |
| `tokens_out` | `int` | yes | Output / completion token count |
| `latency_ms` | `float` | yes | End-to-end latency in milliseconds |
| `query_text` | `str` | no | First 500 chars of the user message (dashboard preview) |
| `application` | `str` | no | Override the default application label for this entry |

### `await tl.alog(*, model, tokens_in, tokens_out, latency_ms, ...)`

Async version of `log()`. Always awaits the HTTP call and returns the response dict.

---

## Response Object

Every `client.chat.completions.create()` call returns a `ChatCompletion` object:

```python
response = client.chat.completions.create(model="gpt4o-mini", messages=[...])

response.choices[0].message.content   # str  — the AI's reply
response.choices[0].message.role      # str  — always "assistant"
response.choices[0].finish_reason     # str  — always "stop"

response.usage.prompt_tokens          # int  — input tokens
response.usage.completion_tokens      # int  — output tokens
response.usage.total_tokens           # int  — prompt + completion

response.cost.usd                     # float — cost in US dollars
response.cost.inr                     # float — cost in Indian rupees

response.latency_ms                   # float — ms from request to first byte of response
response.model                        # str  — model name echoed from backend
response._raw                         # dict — full raw JSON from backend
```

> The `.cost` and `.latency_ms` fields are **extras** that the native OpenAI SDK does not provide. All other fields follow the same path as `openai.types.chat.ChatCompletion` so you can switch between them without changing your code.

---

## Async Support

```python
import asyncio
from tokenlens import TokenLens

tl = TokenLens(api_key="tl-...", base_url="http://localhost:8000")

async def main():

    # ── Option A: async backend chat (no provider key) ────────────────────────
    client   = tl.async_chat()
    response = await client.chat.completions.create(
        model    = "gpt4o-mini",
        messages = [{"role": "user", "content": "Hello!"}],
    )
    print(response.choices[0].message.content)

    # ── Option B: async OpenAI with logging ───────────────────────────────────
    client   = tl.async_openai()   # needs OPENAI_API_KEY
    response = await client.chat.completions.create(
        model    = "gpt-4o-mini",
        messages = [{"role": "user", "content": "Hello!"}],
    )

    # ── Option C: async manual log ────────────────────────────────────────────
    result = await tl.alog(
        model      = "gpt-4o-mini",
        tokens_in  = 150,
        tokens_out = 42,
        latency_ms = 500.0,
        query_text = "Hello!",
    )
    print(result)
    # {"usage_id": "...", "cost_usd": 0.00002745, "cost_inr": 0.00233325}

asyncio.run(main())
```

---

## Cost Utilities

Calculate cost locally without making any network call:

```python
from tokenlens.pricing import compute_cost, list_models

# Basic cost calculation
cost = compute_cost("gpt-4o-mini", tokens_in=150, tokens_out=42)
print(cost)
# {"usd": 0.00002745, "inr": 0.00233325}

# Custom exchange rate
cost = compute_cost("gpt-4o-mini", tokens_in=150, tokens_out=42, usd_to_inr=84.5)

# Custom pricing (for models not in the table, or negotiated rates)
cost = compute_cost(
    "my-custom-model",
    tokens_in  = 1000,
    tokens_out = 500,
    custom_pricing = {"input": 0.002 / 1_000_000, "output": 0.008 / 1_000_000},
)

# List all models in the pricing table
print(list_models())
```

---

## Supported Models & Pricing

The SDK ships with a built-in pricing table. The backend uses the same table to compute cost server-side.

### OpenAI

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|---|---|---|
| `gpt-4o` | $5.00 | $20.00 |
| `gpt-4o-mini` | $0.15 | $0.60 |
| `gpt-4-turbo` | $10.00 | $30.00 |
| `gpt-4` | $30.00 | $60.00 |
| `gpt-3.5-turbo` | $0.50 | $1.50 |
| `o1` | $15.00 | $60.00 |
| `o1-mini` | $3.00 | $12.00 |
| `o3` | $10.00 | $40.00 |
| `o3-mini` | $1.10 | $4.40 |

### Anthropic

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|---|---|---|
| `claude-opus-4-8` | $15.00 | $75.00 |
| `claude-sonnet-4-6` | $3.00 | $15.00 |
| `claude-haiku-4-5-20251001` | $0.80 | $4.00 |
| `claude-3-5-sonnet-20241022` | $3.00 | $15.00 |
| `claude-3-5-haiku-20241022` | $0.80 | $4.00 |
| `claude-3-opus-20240229` | $15.00 | $75.00 |
| `claude-3-haiku-20240307` | $0.25 | $1.25 |

### Google

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|---|---|---|
| `gemini-1.5-pro` | $1.25 | $5.00 |
| `gemini-1.5-flash` | $0.075 | $0.30 |
| `gemini-2.0-flash` | $0.10 | $0.40 |
| `gemini-2.0-flash-lite` | $0.075 | $0.30 |

### TokenLens Backend Aliases

| Model string | Maps to |
|---|---|
| `"gemma"` | Ollama local model |
| `"gpt4"` | OpenAI GPT-4 |
| `"gpt4o-mini"` | OpenAI GPT-4o Mini |

> Models not in the table are logged at a minimal fallback rate ($0.001/$0.002 per 1M tokens). Pass `custom_pricing` to `compute_cost()` for accurate local estimates.

---

## Error Handling

The SDK never crashes your application by default (`raise_on_error=False`). Failures are logged as warnings via Python's `logging` module.

```python
import logging
logging.basicConfig(level=logging.WARNING)

tl = TokenLens(api_key="tl-...", raise_on_error=False)  # default — safe
tl.log(model="gpt-4o-mini", tokens_in=100, tokens_out=50, latency_ms=500)
# If backend is down: logs a warning, returns None, does NOT raise
```

**Strict mode** — raise on any failure (useful for tests):

```python
from tokenlens import TokenLens, LoggingError, AuthError

tl = TokenLens(api_key="tl-...", raise_on_error=True)

try:
    tl.log(model="gpt-4o-mini", tokens_in=100, tokens_out=50, latency_ms=500)
except LoggingError as e:
    print(f"Logging failed: {e}")
```

### Exception Types

| Exception | When raised |
|---|---|
| `AuthError` | `api_key` is empty or does not start with `tl-` |
| `LoggingError` | Backend returned a non-200 status, or the connection timed out |
| `TokenLensError` | Base class for all SDK exceptions |

---

## Where Data Is Saved

Every call saves data to the TokenLens backend database:

| Call | `query_analytics` table | `api_usage` table |
|---|---|---|
| `tl.chat()` | Yes (via backend background task) | Yes (via `/v1/log` post-call) |
| `tl.openai()` | No | Yes |
| `tl.anthropic()` | No | Yes |
| `tl.log()` | No | Yes |

- **`query_analytics`** — visible in **Analytics → User History** in the dashboard
- **`api_usage`** — visible in **Analytics → SDK Usage** in the dashboard

---

## How `test_tokenlens.py` Works

```python
from tokenlens import TokenLens
```
Imports the `TokenLens` class from the installed `tokenlens-sdk` package.

---

```python
tl = TokenLens(
    api_key  = "tl-VJomad6oeJgDbk4D4aW8qLllrGpjmC4fPhTHN0Awc_4",
    base_url = "http://localhost:8000",
)
```
Creates the SDK client. Validates that the key starts with `tl-`. No network call yet.

---

```python
client = tl.chat()
```
Creates a `TokenLensChatClient`. Generates a random UUID as the `session_id`. No network call yet.

---

```python
response = client.chat.completions.create(
    model    = "gpt4o-mini",
    messages = [{"role": "user", "content": "Hi!"}],
)
```

This triggers the following step-by-step chain:

```
Step 1 — SDK extracts last user message
         "Hi!" from messages list

Step 2 — SDK sends POST http://localhost:8000/chat
         Headers: { Authorization: "Bearer tl-VJomad6..." }
         Body:    { session_id: "uuid-abc", user_id: "sdk",
                    message: "Hi!", model: "gpt4o-mini" }

Step 3 — FirebaseAuthMiddleware on backend
         Sees "Bearer tl-..." prefix
         Looks up key hash in api_keys table
         Sets request.state.user = { uid: "firebase-uid-of-key-owner" }

Step 4 — /chat endpoint on backend
         Overrides user_id with the real Firebase UID from the key
         Calls LLM (OpenAI or Ollama, from backend .env)
         Counts tokens, computes cost in USD and INR
         Returns HTTP 200 immediately with:
           { response: "Hello! ...", usage: {...}, cost: {...}, latency_ms: ... }
         Schedules background task: _persist_query() → writes to query_analytics

Step 5 — SDK receives JSON, wraps in ChatCompletion object

Step 6 — SDK fires background POST http://localhost:8000/v1/log
         (in a daemon thread — does not block your code)
         This writes to api_usage table (SDK usage view in dashboard)
```

---

```python
print(response.choices[0].message.content)
```
The AI's reply text. Same path as the real OpenAI SDK.

---

```python
print(f"Tokens: {response.usage.total_tokens}  |  Cost: ${response.cost.usd:.8f}")
```
Token count and cost — returned directly by the TokenLens backend, not available from the native OpenAI SDK.

Example output:
```
Hello! How can I help you today?
Tokens: 192  |  Cost: $0.00002880
```

---

## File Structure

```
sdk/
├── README.md                          ← this file
├── pyproject.toml                     ← package metadata & build config
├── tokenlens/
│   ├── __init__.py                    ← public exports: TokenLens, exceptions
│   ├── client.py                      ← TokenLens class (all methods)
│   ├── chat.py                        ← TokenLensChatClient (tl.chat())
│   ├── pricing.py                     ← compute_cost(), list_models(), pricing table
│   ├── exceptions.py                  ← TokenLensError, AuthError, LoggingError
│   └── wrappers/
│       ├── openai.py                  ← proxy for openai.OpenAI / AsyncOpenAI
│       └── anthropic.py               ← proxy for anthropic.Anthropic / AsyncAnthropic
└── examples/
    ├── openai_example.py              ← tl.openai() demo
    ├── anthropic_example.py           ← tl.anthropic() demo
    └── async_example.py               ← async OpenAI demo
```

---

## Backend Endpoint Reference

The SDK communicates with two backend endpoints:

| Endpoint | Used by | What it does |
|---|---|---|
| `POST /chat` | `tl.chat()` | Full LLM call through backend, saves to `query_analytics` |
| `POST /v1/log` | `tl.log()`, `tl.openai()`, `tl.anthropic()`, `tl.chat()` | Saves token/cost data to `api_usage` |

Both require `Authorization: Bearer tl-<your-key>`.
