from tests.conftest import ALICE_HEADERS


def test_invalid_token_returns_openai_shaped_401(client):
    response = client.get("/models", headers={"Authorization": "Bearer sk-proxy-wrong"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "invalid_api_key"


def test_admin_route_requires_admin_flag(client):
    response = client.get("/admin/users", headers=ALICE_HEADERS)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "insufficient_permissions"
