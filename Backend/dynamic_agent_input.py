import json
import os
import sys

from dotenv import load_dotenv
from tokenlens import TokenLens

load_dotenv(override=True)
load_dotenv("Backend/.env", override=False)

TOKENLENS_KEY = os.getenv("TOKENLENS_KEY", "")
TOKENLENS_URL = os.getenv("TOKENLENS_URL", "http://localhost:8000")

if not TOKENLENS_KEY:
    print("ERROR: TOKENLENS_KEY not set in .env")
    sys.exit(1)

tl = TokenLens(
    api_key=TOKENLENS_KEY,
    base_url=TOKENLENS_URL,
    agent_name="dynamic-agent",
    background=False,
)

client = tl.openai()


# ── Local tool implementations ────────────────────────────────────────────────

def get_weather(city: str) -> str:
    return f"It's always sunny in {city}!"


def create_daily_thought() -> str:
    resp = tl.openai().chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": "Generate a short, unique inspirational daily thought in one or two sentences."}],
    )
    return resp.choices[0].message.content


TOOL_REGISTRY = {
    "get_weather":          lambda args: get_weather(args["city"]),
    "create_daily_thought": lambda args: create_daily_thought(),
}

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


# ── Agent loop ────────────────────────────────────────────────────────────────

def run_agent(user_input: str) -> str:
    messages = [{"role": "user", "content": user_input}]

    while True:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=messages,
            tools=TOOLS,
            tool_choice="auto",
        )

        msg = response.choices[0].message
        messages.append(msg)

        if not msg.tool_calls:
            return msg.content

        for tc in msg.tool_calls:
            fn_name = tc.function.name
            fn_args = json.loads(tc.function.arguments or "{}")
            handler  = TOOL_REGISTRY.get(fn_name)
            result   = str(handler(fn_args)) if handler else f"Unknown tool: {fn_name}"

            messages.append({
                "role":         "tool",
                "tool_call_id": tc.id,
                "name":         fn_name,
                "content":      result,
            })


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python dynamic_agent_input.py "<your message>"')
        sys.exit(1)

    answer = run_agent(" ".join(sys.argv[1:]))
    print(answer)

from langchain.agents import create_agent
from langchain_openai import ChatOpenAI

load_dotenv(override=True)

# --- DEBUG: confirm which key got loaded ---
key = os.getenv("OPENAI_API_KEY")
if key:
    print(f"Loaded key: starts {key[:8]}... ends ...{key[-4:]}  (length {len(key)})")
else:
    print("No OPENAI_API_KEY found in environment!")
# -------------------------------------------

def get_weather(city: str) -> str:
    """Get weather for a given city."""
    return f"It's always sunny in {city}!"

def create_daily_thought() -> str:
    """Generate an inspirational daily thought using the LLM."""
    llm = ChatOpenAI(model="gpt-4o-mini")
    response = llm.invoke("Generate a short, unique inspirational daily thought in one or two sentences.")
    return response.content

agent = create_agent(
    model="openai:gpt-4o",    
    tools=[get_weather, create_daily_thought],
    system_prompt="You are a helpful assistant. Make sure that you only respond with whatever is coming as input to the agent, and do not add any extra commentary or explanation.",
)

if len(sys.argv) < 2:
    print("Usage: python dynamic_agent_input.py \"<your message>\"")
    sys.exit(1)

user_input = " ".join(sys.argv[1:])

result = agent.invoke({"messages": [{"role": "user", "content": user_input}]})
print(result["messages"][-1].content)