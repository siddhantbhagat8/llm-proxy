from tests.conftest import ALICE_HEADERS


def test_usage_reports_limits_and_zeroed_standing(client):
    response = client.get("/usage", headers=ALICE_HEADERS)
    assert response.status_code == 200
    body = response.json()
    assert body["user"]["name"] == "alice"
    assert body["limits"] == {
        "requests_per_minute": 60,
        "tokens_per_day": 1_000_000,
        "lifetime_spend_dollars": 5.0,
    }
    assert body["usage"]["total_requests"] == 0
    assert body["usage"]["lifetime_spend_dollars"] == 0
