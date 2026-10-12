"""Explicit metric definitions, including safe behavior for all-zero targets."""

from __future__ import annotations

import numpy as np


def regression_metrics(actual: np.ndarray, prediction: np.ndarray) -> dict[str, float | None]:
    actual = np.asarray(actual, dtype=float)
    prediction = np.asarray(prediction, dtype=float)
    if actual.shape != prediction.shape or actual.size == 0:
        raise ValueError("Metrics require non-empty, equally shaped arrays.")
    if not np.isfinite(actual).all() or not np.isfinite(prediction).all():
        raise ValueError("Metrics require finite inputs.")
    errors = prediction - actual
    denominator = np.abs(actual).sum()
    return {
        "mae": float(np.abs(errors).mean()),
        "rmse": float(np.sqrt(np.square(errors).mean())),
        "wape": float(100 * np.abs(errors).sum() / denominator) if denominator > 0 else None,
    }


def calibration_radii(
    actual: np.ndarray, prediction: np.ndarray, scale: np.ndarray, horizons: np.ndarray, coverage: float = 0.9
) -> np.ndarray:
    """Finite-sample quantile of normalized absolute errors, separately for each horizon."""
    if not 0 < coverage < 1:
        raise ValueError("Coverage must be strictly between zero and one.")
    residual = np.abs(np.asarray(actual) - np.asarray(prediction)) / np.asarray(scale)
    radii = []
    for horizon in range(1, 25):
        scores = np.sort(residual[np.asarray(horizons) == horizon])
        if len(scores) == 0 or not np.isfinite(scores).all():
            raise ValueError(f"Missing or non-finite calibration scores for horizon {horizon}.")
        rank = min(int(np.ceil((len(scores) + 1) * coverage)), len(scores))
        radii.append(float(scores[rank - 1]))
    return np.asarray(radii)


def prediction_intervals(
    prediction: np.ndarray, scale: np.ndarray, horizons: np.ndarray, radii: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    width = radii[np.asarray(horizons, dtype=int) - 1] * scale
    return np.maximum(0, prediction - width), prediction + width
