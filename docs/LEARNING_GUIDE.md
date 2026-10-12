# WattScope technical walkthrough

WattScope forecasts the next 24 hourly energy readings from historical UCI electricity data. It compares scikit-learn's `HistGradientBoostingRegressor` with daily and weekly seasonal baselines, serves forecasts through FastAPI, and displays them in a dashboard.

This guide follows the data from the forecast origin through evaluation and serving. The API uses the stored historical dataset; it has no live meter connection.

## Forecast contract

Start with the prediction time, also called the forecast origin. If `t` is the last observed hour, WattScope predicts hours `t + 1` through `t + 24`. At that moment, it may use measurements at or before `t` and calendar information that is already known.

Identify the actual target column, its unit, and how the pipeline aggregates raw measurements into hourly observations. An hourly mean of power in kW is different from hourly energy in kWh. Labels, API responses, metrics, and charts must use the same interpretation.

Trace one forecast from input history to features, model output, API response, and dashboard. Be able to explain what happens when there is not enough history or an hour is missing.

## Data boundaries

Follow the chronological order of the training, validation, calibration, and test periods. Each period has a different job:

| Period | Allowed purpose |
| --- | --- |
| Training | Fit the model and any learned preprocessing. |
| Validation | Compare model choices and select settings. |
| Calibration | Estimate the error distribution used for prediction intervals after model choices are fixed. |
| Test | Report the final evaluation on later, untouched observations. |

Earlier observations may provide history for a later forecast when they were already available at its origin. That is different from fitting on later outcomes. Inspect the target timestamps as well as the row timestamps: a training origin must not introduce labels from a held-out period.

Common leakage mistakes to look for:

- Randomly splitting adjacent time-series rows, so future patterns enter training.
- Computing a rolling mean that includes the value being predicted, using a centered window, or forgetting to shift a feature.
- Using actual future consumption to build features for later hours in the same 24-hour forecast.
- Filling a historical gap with a future reading or fitting an imputer on all periods.
- Choosing features, hyperparameters, or interval widths after looking at test performance.
- Reusing calibration outcomes to tune the predictor and still calling them independent calibration data.

Calendar features such as the target hour and weekday are known in advance. Future meter readings are not. Check every feature against that distinction.

## Baselines and model

The daily seasonal baseline copies the reading from 24 hours before each target hour. For a 24-hour forecast issued at `t`, its source for horizon `h` is `t + h - 24`, which is at or before `t`. The weekly baseline uses `t + h - 168`. Both require enough available history.

Electricity demand can repeat by hour and weekday, making these baselines useful references. Their measured errors show whether the learned model improves on those seasonal patterns.

`HistGradientBoostingRegressor` builds an additive sequence of decision trees, with numeric features grouped into bins to make training more efficient. It can learn nonlinear relationships without requiring a neural network. Inspect which features and forecast horizons the implementation supplies to it; do not describe a direct, recursive, or shared-horizon strategy unless the code actually uses it.

Compare all methods on the same eligible forecast origins, horizons, and target observations. If a baseline cannot produce a forecast for a row, silently dropping that row for only one method makes the comparison misleading.

## Evaluation metrics

For actual values `y_i` and predictions `p_i`:

```text
MAE  = mean(abs(y_i - p_i))
WAPE = sum(abs(y_i - p_i)) / sum(abs(y_i))
```

MAE answers: “How large is the typical absolute error in the target's unit?” WAPE expresses aggregate absolute error relative to aggregate demand; multiply by 100 to display it as a percentage. WAPE is undefined when its denominator is zero. It is not the average of each observation's percentage error.

Use both because they answer different questions. An overall WAPE can be dominated by high-demand observations and hide poor performance on quieter hours. Inspect errors by forecast horizon and time of day, and inspect whether peak demand is systematically underestimated.

Before citing a result, check the test dates, sample count, units, missing-data policy, and whether overlapping forecast windows count the same target hour more than once. Report the protocol with the metric. This guide contains no measured performance claims; use the reports from a reproducible run.

## Prediction intervals

Trace how the implementation constructs intervals from the separate chronological calibration period. Explain which residuals it uses, how the requested coverage affects the chosen quantile, and whether calibration is pooled or separated by forecast horizon.

An interval is a range for a future observation. It is not a confidence interval for a model parameter. Its nominal coverage is a target, not a guarantee about every individual forecast.

On the untouched test period, measure both:

- **Empirical coverage:** the fraction of actual observations inside their intervals.
- **Interval width:** how wide the ranges are, in the target's unit.

Wide intervals can achieve good coverage while being unhelpful. Narrow intervals can look attractive while missing many observations. Evaluate both, ideally by horizon. Coverage for individual hourly predictions does not mean the entire 24-hour path is covered with the same probability.

Chronological calibration avoids using later labels to set earlier intervals. It does not remove distribution shift or automatically satisfy independence assumptions. Changes in demand patterns can make historical calibration less reliable. Any clipping of negative bounds or other postprocessing must be documented and evaluated using the final intervals shown to the user.

## API and dashboard

Open the FastAPI documentation and the dashboard. Confirm that the forecast origin, target timestamps, units, and interval labels are clear. Check that the example is presented as a historical replay or demo. It should not imply that the project has access to a current smart meter.

Evaluate the forecast contract, data boundaries, baseline comparisons and empirical interval coverage together.

## Review questions

1. What information is available when a forecast is issued, and what information is unavailable?
2. How are the raw UCI measurements aggregated, and what is the target's unit?
3. Why do you need both daily and weekly seasonal baselines?
4. How can a lag or rolling feature leak future information even with a chronological split?
5. How does the code generate the 24 horizons, and what tradeoffs does that strategy make?
6. Why use `HistGradientBoostingRegressor`, and what evidence would justify a different model?
7. How do MAE and WAPE differ, and when is WAPE undefined or misleading?
8. What are the separate roles of validation, calibration, and test data?
9. How are intervals calibrated, and what do coverage and width reveal together?
10. What would need to change before this historical demo could support live forecasting?

## Suggested extensions

Record each experiment's configuration, changes and observed results.

1. **Audit one forecast origin.** Trace the source timestamp of every lag and rolling feature for all 24 horizons. Add a focused check that fails if a measurement feature accesses a time after the forecast origin. Explain why known calendar features are allowed.
2. **Extend the evaluation.** Add an error breakdown by weekday, using the same test observations for each model. Write a short interpretation of the actual output, including a case where the baseline performs well. Keep the test set out of model selection; if the analysis prompts a new model choice, use a new later holdout for its final assessment.
3. **Extend the uncertainty report.** Add coverage and mean interval width by horizon for at least two nominal coverage levels. Use calibration data to construct the intervals and test data only to assess them. Explain the width/coverage tradeoff and why hourly coverage is different from coverage of the complete forecast path.
