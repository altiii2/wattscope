"""Deterministic pooled histogram boosting; normalization uses past readings only."""

from __future__ import annotations

import numpy as np
from sklearn.ensemble import HistGradientBoostingRegressor

from wattscope.features import Examples

CONFIGURATIONS = [
    {"max_leaf_nodes": 15, "l2_regularization": 1.0, "max_iter": 120},
    {"max_leaf_nodes": 31, "l2_regularization": 1.0, "max_iter": 180},
    {"max_leaf_nodes": 31, "l2_regularization": 5.0, "max_iter": 180},
]


def fit_model(examples: Examples, parameters: dict) -> HistGradientBoostingRegressor:
    model = HistGradientBoostingRegressor(
        learning_rate=0.06,
        min_samples_leaf=40,
        early_stopping=False,
        random_state=42,
        **parameters,
    )
    model.fit(examples.x, examples.y / examples.scale)
    return model


def predict_model(model: HistGradientBoostingRegressor, x: np.ndarray, scale: np.ndarray) -> np.ndarray:
    return np.maximum(0, model.predict(x) * scale)
