import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ADMIN_HEADERS = {"Authorization": "Bearer sk-proxy-test-admin"}
ALICE_HEADERS = {"Authorization": "Bearer sk-proxy-test-alice"}

CHAT_RESPONSE = {
    "id": "chatcmpl-test",
    "object": "chat.completion",
    "created": 1755216000,
    "model": "llama3.2:1b",
    "choices": [
        {
            "index": 0,
            "message": {"role": "assistant", "content": "Hello!"},
            "finish_reason": "stop",
        }
    ],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}

STREAM_BODY = (
    b'data: {"object":"chat.completion.chunk","choices":[{"delta":{"role":"assistant","content":"Hi"}}]}\n\n'
    b'data: {"object":"chat.completion.chunk","choices":[{"delta":{},"finish_reason":"stop"}]}\n\n'
    b'data: {"object":"chat.completion.chunk","choices":[],'
    b'"usage":{"prompt_tokens":10,"completion_tokens":5,"total_tokens":15}}\n\n'
    b"data: [DONE]\n\n"
)


def fake_ollama(request: httpx.Request) -> httpx.Response:
    assert request.url.path == "/v1/chat/completions"
    payload = json.loads(request.content)
    if payload.get("stream"):
        assert payload["stream_options"]["include_usage"] is True
        return httpx.Response(
            200, content=STREAM_BODY, headers={"content-type": "text/event-stream"}
        )
    return httpx.Response(200, json=CHAT_RESPONSE)


@pytest.fixture
def client(tmp_path):
    app = create_app(
        database_path=str(tmp_path / "test.db"),
        ollama_transport=httpx.MockTransport(fake_ollama),
    )
    with TestClient(app) as test_client:
        user_service = app.state.user_service
        user_service.create_user("admin", is_admin=True, token="sk-proxy-test-admin")
        user_service.create_user("alice", token="sk-proxy-test-alice")
        yield test_client


def chat_request(model: str = "llama3.2:1b", stream: bool = False) -> dict:
    body: dict = {"model": model, "messages": [{"role": "user", "content": "hi"}]}
    if stream:
        body["stream"] = True
    return body
