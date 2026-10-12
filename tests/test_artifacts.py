"""Audit the shipped real-data results and run inference with the trained artifact."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from wattscope.api import create_app, get_service
from wattscope.metrics import regression_metrics
from wattscope.service import ForecastService

ROOT = Path(__file__).resolve().parents[1]
pytestmark = pytest.mark.skipif(
    not (ROOT / "models" / "model.joblib").exists(),
    reason="Run the training pipeline to create the real-data artifact.",
)


def test_recorded_metrics_match_prediction_level_evidence():
    report = json.loads((ROOT / "reports" / "results.json").read_text(encoding="utf-8"))
    predictions = pd.read_csv(ROOT / "reports" / "predictions.csv.gz")
    assert len(predictions) == report["validation"]["test_examples"] == 92 * 24 * 8
    for name, column in [
        ("model", "prediction"),
        ("previous_day", "previous_day"),
        ("previous_week", "previous_week"),
    ]:
        recomputed = regression_metrics(predictions.actual, predictions[column])
        for metric, value in recomputed.items():
            assert value == pytest.approx(report["metrics"][name][metric], abs=1e-6)


def test_real_api_returns_a_complete_forecast_and_rejects_unsupported_origins():
    service = ForecastService(ROOT)
    app = create_app()
    app.dependency_overrides[get_service] = lambda: service
    with TestClient(app) as client:
        response = client.get("/api/forecast", params={"client_id": "MT_004"})
        assert response.status_code == 200
        payload = response.json()
        assert len(payload["forecast"]) == 24
        assert all(row["lower"] <= row["prediction"] <= row["upper"] for row in payload["forecast"])
        assert all(row["actual"] is not None for row in payload["forecast"])
        assert (
            client.get(
                "/api/forecast", params={"client_id": "MT_001", "origin": "2014-10-01T12:00"}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/forecast", params={"client_id": "MT_001", "origin": "2014-01-01T00:00"}
            ).status_code
            == 422
        )
        assert (
            client.get(
                "/api/forecast", params={"client_id": "MT_001", "origin": "2014-09-29T00:00"}
            ).status_code
            == 422
        )


def test_future_actuals_can_change_without_changing_predictions():
    service = ForecastService(ROOT)
    origin = "2014-12-15T00:00:00"
    before = service.forecast("MT_001", origin)
    service.frame.loc[service.frame.index > pd.Timestamp(origin)] *= 10
    after = service.forecast("MT_001", origin)
    np.testing.assert_array_equal(
        [row["prediction"] for row in before["forecast"]], [row["prediction"] for row in after["forecast"]]
    )
    assert before["forecast"][0]["actual"] != after["forecast"][0]["actual"]


def test_forecast_beyond_the_dataset_never_invents_actual_values():
    payload = ForecastService(ROOT).forecast("MT_001", "2015-01-01T00:00:00")
    assert len(payload["forecast"]) == 24
    assert all(row["actual"] is None for row in payload["forecast"])
    assert all(np.isfinite(row["prediction"]) for row in payload["forecast"])
