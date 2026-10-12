"""Inference shared by API and CLI; observations after origin are never features."""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

from wattscope.data import load_hourly
from wattscope.features import HORIZON, LOOKBACK, origin_features
from wattscope.metrics import prediction_intervals
from wattscope.modeling import predict_model


class ForecastService:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.frame = load_hourly(self.root)
        self.bundle = joblib.load(self.root / "models" / "model.joblib")
        self.report = json.loads((self.root / "reports" / "results.json").read_text(encoding="utf-8"))
        if self.bundle["clients"] != list(self.frame.columns):
            raise ValueError("Model client order does not match the processed data.")

    def overview(self) -> dict:
        return self.report

    def clients(self) -> list[dict]:
        return [
            {
                "client_id": name,
                "label": f"Client {name.split('_')[-1]}",
                "mean_load": float(self.frame[name].mean()),
            }
            for name in self.frame.columns
        ]

    def forecast(self, client_id: str, origin: str | None = None) -> dict:
        if client_id not in self.frame.columns:
            raise KeyError(f"Unknown client: {client_id}")
        try:
            stamp = pd.Timestamp(origin or self.report["default_origin"])
        except (ValueError, TypeError) as error:
            raise ValueError("Origin must be a valid ISO timestamp.") from error
        if pd.isna(stamp) or stamp.tzinfo is not None or stamp != stamp.floor("D"):
            raise ValueError("Origin must be timezone-naive midnight (00:00) in the source clock.")
        forecast_start = pd.Timestamp(self.bundle.get("forecast_start", self.report["data"]["test_start"]))
        if stamp < forecast_start:
            raise ValueError(
                f"Origin must be on or after {forecast_start.isoformat()}, after fitting and calibration."
            )
        location = self.frame.index.get_indexer([stamp])[0]
        if location < LOOKBACK - 1:
            raise ValueError("Origin must be an observed hour with seven days of available history.")
        history = self.frame.iloc[location - LOOKBACK + 1 : location + 1]
        x, scale = origin_features(history.to_numpy(), stamp)
        prediction = predict_model(self.bundle["model"], x, scale)
        count = self.frame.shape[1]
        horizons = np.repeat(np.arange(1, HORIZON + 1), count)
        lower, upper = prediction_intervals(prediction, scale, horizons, self.bundle["radii"])
        position = self.frame.columns.get_loc(client_id)
        rows = []
        for step in range(1, HORIZON + 1):
            target = stamp + pd.Timedelta(hours=step)
            index = (step - 1) * count + position
            rows.append(
                {
                    "timestamp": target.isoformat(),
                    "prediction": float(prediction[index]),
                    "lower": float(lower[index]),
                    "upper": float(upper[index]),
                    "previous_day": float(history.iloc[-24 + step - 1, position]),
                    "previous_week": float(history.iloc[step - 1, position]),
                    "actual": float(self.frame.at[target, client_id]) if target in self.frame.index else None,
                }
            )
        return {
            "client_id": client_id,
            "origin": stamp.isoformat(),
            "unit": "kWh",
            "history": [
                {"timestamp": time.isoformat(), "actual": float(value)}
                for time, value in history[client_id].iloc[-48:].items()
            ],
            "forecast": rows,
            "model_name": "Histogram gradient boosting",
            "interval_note": self.report["model"]["interval_note"],
        }
