from tokenlens import TokenLens

tl = TokenLens(
    api_key="tl-VJomad6oeJgDbk4D4aW8qLllrGpjmC4fPhTHN0Awc_4",
    base_url="http://localhost:8000",
)

# No OPENAI_API_KEY needed — the backend uses its own configured LLM keys.
client = tl.chat()

response = client.chat.completions.create(
    model="gpt4o-mini",
    messages=[{"role": "user", "content": "Hi!"}],
)

print(response.choices[0].message.content)
print(f"Tokens: {response.usage.total_tokens}  |  Cost: ${response.cost.usd:.8f}")
