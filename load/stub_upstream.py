"""A stand-in for a production-capacity LLM provider (DESIGN.md 3.7).

Serves a canned OpenAI-shaped chat completion — with a usage object, so the
proxy's billing path is fully exercised — after ~50ms of simulated provider
latency. Lives outside app/ so the proxy binary under test contains zero test
scaffolding; the proxy is pointed here via OLLAMA_BASE_URL.

Run from the repo root: uv run uvicorn load.stub_upstream:app --port 11435 --log-level warning
"""

import asyncio
import json

LATENCY_SECONDS = 0.05

RESPONSE_BODY = json.dumps(
    {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": 0,
        "model": "llama3.2:1b",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": "2 + 2 equals 4."},
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 33, "completion_tokens": 9, "total_tokens": 42},
    }
).encode()


async def app(scope, receive, send) -> None:
    if scope["type"] != "http":
        return
    while True:  # drain the request body before responding
        message = await receive()
        if message["type"] != "http.request" or not message.get("more_body"):
            break
    await asyncio.sleep(LATENCY_SECONDS)
    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [(b"content-type", b"application/json")],
        }
    )
    await send({"type": "http.response.body", "body": RESPONSE_BODY})
