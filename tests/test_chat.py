from tests.conftest import ALICE_HEADERS, chat_request


def test_chat_completion_forwards_and_records_usage(client):
    response = client.post(
        "/chat/completions", json=chat_request(), headers=ALICE_HEADERS
    )
    assert response.status_code == 200
    assert response.json()["usage"]["total_tokens"] == 15
    usage = client.get("/usage", headers=ALICE_HEADERS).json()["usage"]
    assert usage["total_requests"] == 1
    assert usage["lifetime_tokens"] == 15
    assert usage["lifetime_spend_dollars"] > 0


def test_chat_completion_accepts_v1_prefix(client):
    response = client.post(
        "/v1/chat/completions", json=chat_request(), headers=ALICE_HEADERS
    )
    assert response.status_code == 200


def test_streaming_passthrough_and_usage_recording(client):
    with client.stream(
        "POST",
        "/chat/completions",
        json=chat_request(stream=True),
        headers=ALICE_HEADERS,
    ) as response:
        assert response.status_code == 200
        body = b"".join(response.iter_bytes()).decode()
    assert '"content":"Hi"' in body
    assert body.rstrip().endswith("data: [DONE]")
    usage = client.get("/usage", headers=ALICE_HEADERS).json()["usage"]
    assert usage["lifetime_tokens"] == 15


def test_unknown_model_rejected(client):
    response = client.post(
        "/chat/completions", json=chat_request(model="gpt-4"), headers=ALICE_HEADERS
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "model_not_found"


def test_models_served_from_price_sheet(client):
    response = client.get("/models", headers=ALICE_HEADERS)
    assert response.status_code == 200
    model_ids = {model["id"] for model in response.json()["data"]}
    assert model_ids == {"llama3.2:1b", "moondream"}
