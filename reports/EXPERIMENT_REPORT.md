# WattScope experiment report

Generated from a completed run; no hand-entered performance claims.

## Protocol

- Data: original UCI electricity readings; fixed first eight clients; hourly kWh.
- Train origins: 8 January 2013–31 August 2014.
- Hyperparameter selection origins: 1–14 September 2014; minimum validation MAE.
- Final model fit uses origins through 14 September (labels through 15 September 00:00).
- Calibration origins: 16–29 September 2014. No subsequent refit.
- Held-out test: daily midnight origins in October, November and December 2014, 24 hours per origin.
- Earlier test observations may enter later forecast histories, but never model fitting.

## Held-out results

| Method | MAE (kWh) | RMSE (kWh) | WAPE (%) |
| --- | ---: | ---: | ---: |
| Histogram gradient boosting | 6.4038 | 13.2675 | 7.60 |
| Previous-day seasonal naive | 8.3090 | 17.8247 | 9.86 |
| Previous-week seasonal naive | 7.4248 | 14.7315 | 8.81 |

MAE = mean absolute error. RMSE = root mean squared error. WAPE = 100 × sum(abs(error)) / sum(abs(actual)).
Pooled errors weight clients by their load magnitude. Macro-client WAPE and each client's results are available in `results.json`.

## Monthly test folds

| Origin month | Model WAPE (%) | Previous-day WAPE (%) | Previous-week WAPE (%) | Interval coverage |
| --- | ---: | ---: | ---: | ---: |
| 2014-10 | 7.02 | 9.26 | 8.11 | 87.6% |
| 2014-11 | 7.02 | 9.32 | 8.63 | 90.0% |
| 2014-12 | 8.55 | 10.79 | 9.51 | 87.7% |

## Prediction intervals

Nominal 90% pointwise intervals, calibrated on held-out September residuals by horizon. Serial dependence and distribution shift mean 90% coverage is not guaranteed. These are not simultaneous 24-hour path intervals.
Observed test coverage: **88.4%**. Mean interval width: **41.5336 kWh**.
Calibration uses horizon-specific finite-sample quantiles of absolute residuals normalized by the trailing seven-day mean. Lower endpoints are clipped at zero.

## Limitations

- UCI documents DST zero readings in March and combined readings in October; retained, not imputed.
- Leading zeros can represent clients not yet active, rather than physical zero demand.
- Interval-end interpretation is a documented preprocessing assumption, not a timezone correction.
- Historic anonymized consumption cannot establish current or commercial forecasting performance.
- Eight predetermined clients; results do not generalize to all 370 clients or unseen sites.
- Hyperparameters chosen on validation only; the fitted model is not changed after calibration.
- Actual historical observations update the feature history at each daily forecast origin.
- Pooled WAPE weights high-volume clients more heavily; per-client and macro scores are also reported.
- This is a historical benchmark, not a live energy feed or a commercial deployment.
- Three predefined parameter configurations constitute a small search, not an exhaustive optimizer.
- The source does not identify household types, location-specific weather or tariffs; none are inferred.

## Reproducibility

Run `python -m wattscope.cli train` from the repository root.
Processed data SHA-256: `8ff5138d07c4aa03bcae751e2f30e5f66beca5dd0f434733415f9d8ada5d3267`.
Environment: python 3.12.14, numpy 2.3.5, pandas 3.0.1, scikit-learn 1.7.2, scipy 1.18.1, joblib 1.6.0, matplotlib 3.11.2.
Exact predictions, parameter selection and evaluation slices are saved alongside this report.
