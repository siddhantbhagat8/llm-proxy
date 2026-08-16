"""Proves each requirement against a running proxy (:8000) and Ollama (:11434):
basic chat, streaming, moondream vision, and all three limit types — using the
stock openai client, exactly as a user's application would.

Creates (or reuses) an 'admin' and an 'alice' user directly in the database.

Run from the repo root: uv run -m scripts.demo
"""

import httpx
import openai

from app import config, database
from app.services.user_service import UserService

PROXY_URL = "http://localhost:8000"

connection = database.connect(config.DATABASE_PATH)
user_service = UserService(connection)
admin = user_service.get_user_by_name("admin") or user_service.create_user(
    "admin", is_admin=True
)
alice = user_service.get_user_by_name("alice") or user_service.create_user("alice")
connection.close()

ADMIN_HEADERS = {"Authorization": f"Bearer {admin.token}"}
ALICE_TOKEN = alice.token
ALICE_ID = alice.id

# 64x64 solid red PNG (Ollama accepts vision input as base64 data URIs only)
RED_SQUARE_PNG = (
    "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAIAAAAlC+aJAAAAb0lEQVR4nO3PAQkAAAyEwO9feoshgnAB"
    "dLep8QUNyPEFDcjxBQ3I8QUNyPEFDcjxBQ3I8QUNyPEFDcjxBQ3I8QUNyPEFDcjxBQ3I8QUNyPEFDcjx"
    "BQ3I8QUNyPEFDcjxBQ3I8QUNyPEFDcjxBQ3IPanc8OLDQitxAAAAAElFTkSuQmCC"
)

# max_retries=0: the SDK's default retry policy honors Retry-After and would
# silently absorb the 429s this script exists to demonstrate.
client = openai.OpenAI(base_url=PROXY_URL, api_key=ALICE_TOKEN, max_retries=0)


def set_alice_limits(**limits):
    response = httpx.put(
        f"{PROXY_URL}/admin/users/{ALICE_ID}/limits", json=limits, headers=ADMIN_HEADERS
    )
    response.raise_for_status()


def show_alice_usage():
    usage = httpx.get(
        f"{PROXY_URL}/usage", headers={"Authorization": f"Bearer {ALICE_TOKEN}"}
    ).json()
    print(f"   /usage → {usage['usage']}")


print("1. Basic chat (llama3.2:1b)")
completion = client.chat.completions.create(
    model="llama3.2:1b",
    messages=[{"role": "user", "content": "Say hello in exactly five words."}],
)
print(f"   reply: {completion.choices[0].message.content!r}")
print(f"   usage: {completion.usage}")
show_alice_usage()

print("\n2. Streaming chat")
stream = client.chat.completions.create(
    model="llama3.2:1b",
    messages=[{"role": "user", "content": "Count from 1 to 5."}],
    stream=True,
)
chunk_count = 0
text = ""
for chunk in stream:
    chunk_count += 1
    if chunk.choices and chunk.choices[0].delta.content:
        text += chunk.choices[0].delta.content
print(f"   {chunk_count} chunks streamed, reply: {text.strip()!r}")
show_alice_usage()

print("\n3. Vision (moondream, base64 red square)")
completion = client.chat.completions.create(
    model="moondream",
    messages=[
        {
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": "What color is this image? Answer in one short sentence.",
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{RED_SQUARE_PNG}"},
                },
            ],
        }
    ],
    max_tokens=50,
)
print(f"   reply: {completion.choices[0].message.content.strip()!r}")
print(f"   usage: {completion.usage}")
show_alice_usage()

print("\n4. Unknown model rejected")
try:
    client.chat.completions.create(
        model="gpt-4", messages=[{"role": "user", "content": "hi"}]
    )
except openai.NotFoundError as error:
    print(f"   NotFoundError: {error.body}")

already_in_window = httpx.get(
    f"{PROXY_URL}/usage", headers={"Authorization": f"Bearer {ALICE_TOKEN}"}
).json()["usage"]["requests_last_minute"]
rpm_limit = already_in_window + 2
print(
    f"\n5. Requests-per-minute limit (lowered to {rpm_limit}; {already_in_window} already in window)"
)
set_alice_limits(requests_per_minute=rpm_limit)
for attempt in range(1, 4):
    try:
        client.chat.completions.create(
            model="llama3.2:1b",
            messages=[{"role": "user", "content": "hi"}],
            max_tokens=5,
        )
        print(f"   request {attempt}: 200 OK")
    except openai.RateLimitError as error:
        retry_after = error.response.headers.get("retry-after")
        print(
            f"   request {attempt}: RateLimitError (Retry-After: {retry_after}s) {error.body}"
        )

print("\n6. Tokens-per-day limit (lowered to 100)")
set_alice_limits(requests_per_minute=60, tokens_per_day=100)
try:
    client.chat.completions.create(
        model="llama3.2:1b", messages=[{"role": "user", "content": "hi"}]
    )
except openai.RateLimitError as error:
    retry_after = error.response.headers.get("retry-after")
    print(f"   RateLimitError (Retry-After: {retry_after}s) {error.body}")

print("\n7. Lifetime spend cap (lowered to $0.000001)")
set_alice_limits(tokens_per_day=1_000_000, lifetime_spend_dollars=0.000001)
try:
    client.chat.completions.create(
        model="llama3.2:1b", messages=[{"role": "user", "content": "hi"}]
    )
except openai.RateLimitError as error:
    print(f"   RateLimitError: {error.body}")

set_alice_limits(
    requests_per_minute=config.DEFAULT_REQUESTS_PER_MINUTE,
    tokens_per_day=config.DEFAULT_TOKENS_PER_DAY,
    lifetime_spend_dollars=config.DEFAULT_LIFETIME_SPEND_DOLLARS,
)
print("\nAlice's limits restored to defaults. Done.")
