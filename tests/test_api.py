"""Exercise the HTTP contract without data downloads or model training."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from wattscope.api import create_app, get_service


class FakeService:
    def overview(self):
        return {"project_name": "WattScope", "metrics": {"model": {"mae": 1.2}}}

    def clients(self):
        return [{"client_id": "MT_001"}]

    def forecast(self, client_id, origin=None):
        if client_id == "missing":
            raise KeyError(client_id)
        if client_id == "unavailable":
            raise FileNotFoundError("model.joblib")
        if origin == "invalid":
            raise ValueError("origin must be an observed hourly timestamp")
        return {
            "client_id": client_id,
            "origin": origin or "2014-12-15T00:00:00",
            "unit": "kWh",
            "history": [{"timestamp": "2014-12-15T00:00:00", "actual": 4.0}],
            "forecast": [
                {
                    "timestamp": "2014-12-15T01:00:00",
                    "prediction": 4.2,
                    "lower": 3.0,
                    "upper": 5.4,
                    "previous_day": 4.1,
                    "previous_week": 3.9,
                    "actual": 4.0,
                }
            ],
            "model_name": "Test model",
            "interval_note": "Empirical intervals, not a guarantee.",
        }


@pytest.fixture
def client():
    app = create_app()
    app.dependency_overrides[get_service] = lambda: FakeService()
    with TestClient(app) as test_client:
        yield test_client


def test_health_does_not_require_artifacts(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("WATTSCOPE_ROOT", str(tmp_path))
    with TestClient(create_app()) as client:
        assert client.get("/api/health").json() == {"status": "ok", "service": "WattScope"}


def test_dashboard_and_local_assets_are_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "Historical benchmark" in response.text
    for filename in ("app.js", "style.css"):
        assert client.get(f"/static/{filename}").status_code == 200


def test_overview_and_clients(client):
    assert client.get("/api/overview").json()["project_name"] == "WattScope"
    assert client.get("/api/clients").json() == [{"client_id": "MT_001"}]


def test_get_and_post_have_the_same_forecast_contract(client):
    params = {"client_id": "MT_001", "origin": "2014-12-16T00:00:00"}
    get_response = client.get("/api/forecast", params=params)
    post_response = client.post("/api/forecast", json=params)
    assert get_response.status_code == post_response.status_code == 200
    assert get_response.json() == post_response.json()
    assert get_response.json()["forecast"][0]["actual"] == 4.0


def test_origin_can_be_omitted(client):
    assert (
        client.get("/api/forecast", params={"client_id": "MT_001"}).json()["origin"] == "2014-12-15T00:00:00"
    )


@pytest.mark.parametrize(
    "params", [{}, {"client_id": ""}, {"client_id": "   "}, {"client_id": "MT_001", "origin": ""}]
)
def test_invalid_get_input_returns_422(client, params):
    assert client.get("/api/forecast", params=params).status_code == 422


@pytest.mark.parametrize(
    "payload", [{}, {"client_id": ""}, {"client_id": "   "}, {"client_id": "MT_001", "origin": ""}]
)
def test_invalid_post_input_returns_422(client, payload):
    assert client.post("/api/forecast", json=payload).status_code == 422


def test_invalid_window_and_missing_client_are_explained(client):
    assert client.get("/api/forecast", params={"client_id": "MT_001", "origin": "invalid"}).status_code == 422
    assert client.get("/api/forecast", params={"client_id": "missing"}).status_code == 404
    assert client.get("/api/forecast", params={"client_id": "unavailable"}).status_code == 503


def test_missing_artifacts_are_reported_as_503(monkeypatch, tmp_path: Path):
    import wattscope.api as api

    def unavailable(_root):
        raise FileNotFoundError("model.joblib")

    monkeypatch.setenv("WATTSCOPE_ROOT", str(tmp_path))
    monkeypatch.setattr(api, "ForecastService", unavailable)
    get_service.cache_clear()
    try:
        with TestClient(create_app()) as client:
            assert client.get("/api/overview").status_code == 503
            assert client.get("/api/clients").status_code == 503
            assert client.get("/api/forecast", params={"client_id": "MT_001"}).status_code == 503
    finally:
        get_service.cache_clear()
