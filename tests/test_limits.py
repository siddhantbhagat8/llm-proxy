from tests.conftest import ADMIN_HEADERS, ALICE_HEADERS, chat_request

ALICE_ID = 2  # created second in the fixture, after admin


def set_limits(client, **limits):
    response = client.put(
        f"/admin/users/{ALICE_ID}/limits", json=limits, headers=ADMIN_HEADERS
    )
    assert response.status_code == 200


def test_requests_per_minute_limit(client):
    set_limits(client, requests_per_minute=1)
    assert (
        client.post(
            "/chat/completions", json=chat_request(), headers=ALICE_HEADERS
        ).status_code
        == 200
    )
    blocked = client.post(
        "/chat/completions", json=chat_request(), headers=ALICE_HEADERS
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limit_exceeded"
    assert int(blocked.headers["Retry-After"]) >= 1


def test_tokens_per_day_limit(client):
    set_limits(client, tokens_per_day=10)
    assert (
        client.post(
            "/chat/completions", json=chat_request(), headers=ALICE_HEADERS
        ).status_code
        == 200
    )
    blocked = client.post(
        "/chat/completions", json=chat_request(), headers=ALICE_HEADERS
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limit_exceeded"


def test_lifetime_spend_cap(client):
    set_limits(client, lifetime_spend_dollars=0.0)
    blocked = client.post(
        "/chat/completions", json=chat_request(), headers=ALICE_HEADERS
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "insufficient_quota"


def test_rejected_requests_do_not_extend_the_block(client):
    set_limits(client, requests_per_minute=1)
    client.post("/chat/completions", json=chat_request(), headers=ALICE_HEADERS)
    for _ in range(3):
        client.post("/chat/completions", json=chat_request(), headers=ALICE_HEADERS)
    usage = client.get("/usage", headers=ALICE_HEADERS).json()["usage"]
    assert usage["total_requests"] == 1
