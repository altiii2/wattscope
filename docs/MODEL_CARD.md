# Model card: WattScope day-ahead load forecaster

## Intended use

A reproducible benchmark of hourly electricity forecasting, with an API and dashboard for exploring historical forecasts. The evaluated interface supports eight predetermined clients and daily midnight origins in the source clock. Grid control, billing and safety-critical decisions are outside its intended use; commercial savings have not been evaluated.

## Data and targets

- Source: Trindade (2015), UCI *ElectricityLoadDiagrams20112014*, DOI `10.24432/C58C86`.
- License: CC BY 4.0; see the source attribution in the README and `data/metadata.json`.
- Scope: `MT_001` through `MT_008`, selected by source column order before training.
- Target: energy in each of the next 24 hourly intervals, in kWh.
- Preprocessing: sum four quarter-hour kW readings and divide by four. Treat labels as interval ends; discard incomplete hours.
- Clock: original normalized Portuguese local timestamps. This benchmark does not repair the source's documented DST encoding or convert the timestamps to UTC.

## Model and inputs

One pooled scikit-learn histogram gradient boosting regressor uses 21 features: horizon, known target calendar, client code, past seasonal lags and trailing load summaries. The target and load features are normalized by the trailing seven-day mean at each origin. A small floor handles all-zero histories. Predictions are clipped to non-negative values.

Features never use a reading after the origin. For a target at `origin + h` where `h <= 24`, the three seasonal lags are at `target - 24`, `target - 48` and `target - 168` hours, all at or before the origin. The same implementation builds training examples and API inputs.

## Training and evaluation

Three parameter configurations were declared before evaluation and selected by validation MAE. Training, selection, calibration and Q4 testing have distinct chronological roles. The selected configuration is refitted before the calibration window; the final fitted model is then frozen.

The held-out test contains 92 daily origins × 24 horizons × 8 clients = **17,664 predictions**. Past observations update at each origin, including test readings that are already historical at that point. Those observations are not used to refit the model.

See the generated [experiment report](../reports/EXPERIMENT_REPORT.md) and [prediction-level output](../reports/predictions.csv.gz) for the exact scores and monthly breakdown. The original completed run measured:

| Method | Pooled WAPE |
| --- | ---: |
| Histogram gradient boosting | 7.60% |
| Previous-day seasonal naive | 9.86% |
| Previous-week seasonal naive | 8.81% |

These are measured errors on this specific subset and protocol, not expected performance on future deployments. Higher-load clients contribute more to pooled WAPE; macro-client WAPE and all eight client scores are recorded in the full results.

## Uncertainty

Horizon-specific interval widths come from held-out calibration errors, normalized by the trailing load mean. They have nominal 90% pointwise coverage. The completed test observed **88.4% coverage**, which is below nominal coverage. Time dependence and distribution shift prevent a general 90% guarantee. These intervals do not describe simultaneous coverage of the entire next-day path.

## Known limits

- Historical anonymized data provides no evidence of current market performance.
- Eight clients do not establish generalization to all 370 source clients or unseen meters.
- No weather, occupancy, outage, tariff or customer-type information is supplied or inferred.
- Activation zeros, DST artifacts and calendar shifts can produce unusual errors.
- Arbitrary daytime origins, irregular time grids, unseen customers and real-time data are outside the evaluated interface.
- Model serialization uses the project's own trusted artifact. The supplied exact dependency versions are the reference environment for loading it.

## Development and extension

Extension candidates include a larger client subset selected before evaluation, interval recalibration under drift, and richer calendar features evaluated on a new untouched period.
