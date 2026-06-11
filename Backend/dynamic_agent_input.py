import json
import os
import sys

import requests
from dotenv import load_dotenv

load_dotenv(override=True)                          # root .env if it exists
load_dotenv("Backend/.env", override=False)         # fallback to Backend/.env

TOKENLENS_KEY = os.getenv("TOKENLENS_KEY", "")
TOKENLENS_URL = os.getenv("TOKENLENS_URL", "http://localhost:8000")

if not TOKENLENS_KEY:
    print("ERROR: TOKENLENS_KEY not set in .env")
    sys.exit(1)

HEADERS = {
    "Authorization": f"Bearer {TOKENLENS_KEY}",
    "Content-Type": "application/json",
}


# ── Local tool implementations ────────────────────────────────────────────────

def get_weather(city: str) -> str:
    return f"It's always sunny in {city}!"


def create_daily_thought() -> str:
    payload = {
        "agent_name": "daily-thought-agent",
        "model": "gpt-4o-mini",
        "messages": [{"role": "user", "content": "Generate a short, unique inspirational daily thought in one or two sentences."}],
    }
    resp = requests.post(f"{TOKENLENS_URL}/v1/agent/run", headers=HEADERS, json=payload, timeout=60)
    resp.raise_for_status()
    return resp.json()["response"]


TOOL_REGISTRY = {
    "get_weather":         lambda args: get_weather(args["city"]),
    "create_daily_thought": lambda args: create_daily_thought(),
}

# OpenAI function schema — passed to TokenLens so the LLM knows what tools exist
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get weather for a given city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Name of the city"}
                },
                "required": ["city"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_daily_thought",
            "description": "Generate a short inspirational daily thought.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
]


# ── TokenLens call loop ───────────────────────────────────────────────────────

def run_agent(user_input: str) -> str:
    # Start the run
    payload = {
        "agent_name": "dynamic-agent",
        "model":      "gpt-4o-mini",
        "messages":   [{"role": "user", "content": user_input}],
        "tools":      TOOLS,
    }
    resp = requests.post(f"{TOKENLENS_URL}/v1/agent/run", headers=HEADERS, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()

    run_id = data["run_id"]

    # Tool-call loop
    while data["status"] == "tool_pending":
        tool_results = []
        for tc in data["tool_calls"]:
            fn_name = tc["function"]["name"]
            fn_args = json.loads(tc["function"].get("arguments", "{}"))
            handler  = TOOL_REGISTRY.get(fn_name)
            if handler is None:
                result = f"Unknown tool: {fn_name}"
            else:
                result = str(handler(fn_args))

            tool_results.append({
                "tool_call_id": tc["id"],
                "name":         fn_name,
                "content":      result,
            })

        resp = requests.post(
            f"{TOKENLENS_URL}/v1/agent/run/{run_id}/continue",
            headers=HEADERS,
            json={"tool_results": tool_results},
            timeout=60,
        )
        resp.raise_for_status()
        data = resp.json()

    if data["status"] == "error":
        raise RuntimeError(f"Agent run failed: {data.get('error', 'unknown error')}")

    return data["response"]


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python dynamic_agent_input.py "<your message>"')
        sys.exit(1)

    user_input = " ".join(sys.argv[1:])
    answer = run_agent(user_input)
    print(answer)