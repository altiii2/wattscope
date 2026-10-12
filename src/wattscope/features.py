"""Direct forecasts using only observations available at the forecast origin."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

LOOKBACK = 168
HORIZON = 24
FEATURE_NAMES = [
    "horizon",
    "hour_sin",
    "hour_cos",
    "weekday_sin",
    "weekday_cos",
    "month_sin",
    "month_cos",
    "is_weekend",
    "client_code",
    "lag_24",
    "lag_48",
    "lag_168",
    "last_value",
    "mean_24",
    "std_24",
    "min_24",
    "max_24",
    "mean_48",
    "std_168",
    "last_change",
    "log_scale",
]


@dataclass
class Examples:
    x: np.ndarray
    y: np.ndarray
    scale: np.ndarray
    origin: np.ndarray
    target: np.ndarray
    client: np.ndarray
    horizon: np.ndarray
    previous_day: np.ndarray
    previous_week: np.ndarray


def origin_features(history: np.ndarray, origin: pd.Timestamp) -> tuple[np.ndarray, np.ndarray]:
    """Return rows ordered by horizon, then client; history ends exactly at origin."""
    history = np.asarray(history, dtype=float)
    if history.ndim == 1:
        history = history[:, None]
    if history.shape[0] != LOOKBACK:
        raise ValueError(f"Exactly {LOOKBACK} contiguous hourly observations are required.")
    if not np.isfinite(history).all() or np.any(history < 0):
        raise ValueError("History must contain finite, non-negative readings.")
    if origin.tzinfo is not None or origin != origin.floor("h"):
        raise ValueError("Use a timezone-naive timestamp on an exact hour in the source clock.")
    count = history.shape[1]
    scale = np.maximum(history.mean(axis=0), 1e-6)
    normalized = history / scale
    static = np.column_stack(
        [
            normalized[-1],
            normalized[-24:].mean(axis=0),
            normalized[-24:].std(axis=0),
            normalized[-24:].min(axis=0),
            normalized[-24:].max(axis=0),
            normalized[-48:].mean(axis=0),
            normalized.std(axis=0),
            normalized[-1] - normalized[-2],
            np.log1p(scale),
        ]
    )
    blocks = []
    for step in range(1, HORIZON + 1):
        stamp = origin + pd.Timedelta(hours=step)
        calendar = [
            step / HORIZON,
            np.sin(2 * np.pi * stamp.hour / 24),
            np.cos(2 * np.pi * stamp.hour / 24),
            np.sin(2 * np.pi * stamp.dayofweek / 7),
            np.cos(2 * np.pi * stamp.dayofweek / 7),
            np.sin(2 * np.pi * (stamp.month - 1) / 12),
            np.cos(2 * np.pi * (stamp.month - 1) / 12),
            float(stamp.dayofweek >= 5),
        ]
        blocks.append(
            np.column_stack(
                [
                    np.tile(calendar, (count, 1)),
                    np.arange(count),
                    normalized[LOOKBACK - 1 + step - 24],
                    normalized[LOOKBACK - 1 + step - 48],
                    normalized[LOOKBACK - 1 + step - 168],
                    static,
                ]
            )
        )
    return np.vstack(blocks), np.tile(scale, HORIZON)


def build_examples(frame: pd.DataFrame, start: str, stop: str) -> Examples:
    """Daily midnight origins in [start, stop), with 24 future labels per client."""
    starts = pd.date_range(start, pd.Timestamp(stop) - pd.Timedelta(days=1), freq="D")
    arrays: dict[str, list[np.ndarray]] = {key: [] for key in Examples.__dataclass_fields__}
    values = frame.to_numpy(dtype=float)
    count = frame.shape[1]
    names = np.asarray(frame.columns)
    for origin in starts:
        location = frame.index.get_indexer([origin])[0]
        if location < LOOKBACK - 1 or location + HORIZON >= len(frame):
            raise ValueError(f"Insufficient complete history or labels at origin {origin}.")
        history = values[location - LOOKBACK + 1 : location + 1]
        x, scale = origin_features(history, origin)
        future = frame.index[location + 1 : location + HORIZON + 1]
        arrays["x"].append(x)
        arrays["y"].append(values[location + 1 : location + HORIZON + 1].reshape(-1))
        arrays["scale"].append(scale)
        arrays["origin"].append(np.repeat(origin.to_datetime64(), HORIZON * count))
        arrays["target"].append(np.repeat(future.to_numpy(), count))
        arrays["client"].append(np.tile(names, HORIZON))
        arrays["horizon"].append(np.repeat(np.arange(1, HORIZON + 1), count))
        arrays["previous_day"].append(history[-24:].reshape(-1))
        arrays["previous_week"].append(history[:24].reshape(-1))
    if not arrays["x"]:
        raise ValueError("The origin range is empty.")
    return Examples(**{key: np.concatenate(parts, axis=0) for key, parts in arrays.items()})
