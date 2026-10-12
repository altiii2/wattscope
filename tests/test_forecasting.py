"""Tests for temporal leakage, energy units, baseline alignment and interval calibration."""

import numpy as np
import pandas as pd
import pytest

from wattscope.data import aggregate_hourly
from wattscope.features import FEATURE_NAMES, build_examples, origin_features
from wattscope.metrics import calibration_radii, prediction_intervals, regression_metrics


def sample_frame():
    index = pd.date_range("2014-01-01", periods=12 * 24 + 1, freq="h", name="timestamp")
    return pd.DataFrame(
        {"MT_001": np.arange(len(index), dtype=float) + 1, "MT_002": np.arange(len(index), dtype=float) + 3},
        index=index,
    )


def test_energy_conversion_uses_four_interval_end_readings():
    index = pd.date_range("2014-01-01 00:15", periods=8, freq="15min")
    quarter_hour = pd.DataFrame({"MT_001": [8.0] * 8}, index=index)
    hourly = aggregate_hourly(quarter_hour)
    assert hourly.index.tolist() == [pd.Timestamp("2014-01-01 01:00"), pd.Timestamp("2014-01-01 02:00")]
    assert hourly.MT_001.tolist() == [8.0, 8.0]


def test_partial_hour_is_not_treated_as_complete_energy():
    source = pd.DataFrame(
        {"MT_001": [8.0] * 3}, index=pd.date_range("2014-01-01 00:15", periods=3, freq="15min")
    )
    assert aggregate_hourly(source).empty


def test_future_changes_cannot_change_any_forecast_feature():
    original = sample_frame()
    changed = original.copy()
    changed.loc[changed.index > "2014-01-09 00:00"] *= 1000
    left = build_examples(original, "2014-01-09", "2014-01-10")
    right = build_examples(changed, "2014-01-09", "2014-01-10")
    np.testing.assert_array_equal(left.x, right.x)
    np.testing.assert_array_equal(left.scale, right.scale)
    np.testing.assert_array_equal(left.previous_day, right.previous_day)
    assert not np.array_equal(left.y, right.y)


def test_seasonal_baselines_and_horizon_24_end_at_observed_origin():
    frame = sample_frame()
    examples = build_examples(frame, "2014-01-09", "2014-01-10")
    assert examples.x.shape == (48, len(FEATURE_NAMES))
    for index, (target, client) in enumerate(zip(examples.target, examples.client, strict=True)):
        stamp = pd.Timestamp(target)
        assert examples.previous_day[index] == frame.at[stamp - pd.Timedelta(hours=24), client]
        assert examples.previous_week[index] == frame.at[stamp - pd.Timedelta(hours=168), client]
        assert stamp - pd.Timedelta(hours=24) <= pd.Timestamp(examples.origin[index])


def test_missing_history_and_invalid_readings_are_rejected():
    with pytest.raises(ValueError, match="Exactly"):
        origin_features(np.ones((167, 2)), pd.Timestamp("2014-01-09"))
    with pytest.raises(ValueError, match="finite"):
        origin_features(np.full((168, 2), np.nan), pd.Timestamp("2014-01-09"))
    with pytest.raises(ValueError, match="timezone"):
        origin_features(np.ones((168, 2)), pd.Timestamp("2014-01-09", tz="UTC"))


def test_wape_uses_aggregate_energy_and_zero_denominator_is_explicit():
    scores = regression_metrics(np.array([0, 10]), np.array([1, 8]))
    assert scores["mae"] == 1.5
    assert scores["wape"] == 30
    assert regression_metrics(np.zeros(2), np.ones(2))["wape"] is None


def test_calibration_quantile_is_horizon_specific_and_clips_lower_at_zero():
    horizons = np.repeat(np.arange(1, 25), 10)
    actual = np.zeros(240)
    predictions = np.tile(np.arange(1, 11), 24).astype(float)
    radii = calibration_radii(actual, predictions, np.ones(240), horizons)
    np.testing.assert_array_equal(radii, np.repeat(10.0, 24))
    low, high = prediction_intervals(np.array([1.0]), np.array([2.0]), np.array([24]), radii)
    assert low[0] == 0
    assert high[0] == 21


def test_every_origin_target_pair_is_unique_and_ordered():
    examples = build_examples(sample_frame(), "2014-01-09", "2014-01-11")
    keys = list(zip(examples.origin, examples.target, examples.client, strict=True))
    assert len(keys) == len(set(keys))
    assert np.all(examples.target > examples.origin)
    assert np.all(examples.target <= examples.origin + np.timedelta64(24, "h"))
