from tests.conftest import ADMIN_HEADERS


def test_create_user_returns_api_key(client):
    response = client.post(
        "/admin/users", json={"name": "carol"}, headers=ADMIN_HEADERS
    )
    assert response.status_code == 201
    created = response.json()
    assert created["api_key"].startswith("sk-proxy-")
    assert created["limits"]["requests_per_minute"] == 60
    models = client.get(
        "/models", headers={"Authorization": f"Bearer {created['api_key']}"}
    )
    assert models.status_code == 200


def test_list_users_includes_keys_usage_and_limits(client):
    response = client.get("/admin/users", headers=ADMIN_HEADERS)
    assert response.status_code == 200
    users = {user["name"]: user for user in response.json()}
    assert {"admin", "alice"} <= set(users)
    assert users["alice"]["api_key"] == "sk-proxy-test-alice"
    assert users["alice"]["usage"]["total_requests"] == 0


def test_update_limits_sets_and_clears_independently(client):
    response = client.put(
        "/admin/users/2/limits",
        json={"requests_per_minute": 5, "lifetime_spend_dollars": None},
        headers=ADMIN_HEADERS,
    )
    assert response.status_code == 200
    limits = response.json()["limits"]
    assert limits["requests_per_minute"] == 5
    assert limits["lifetime_spend_dollars"] is None
    assert limits["tokens_per_day"] == 1_000_000  # untouched field unchanged
