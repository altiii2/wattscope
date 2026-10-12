"""Run a predeclared chronological experiment and write auditable artifacts."""

from __future__ import annotations

import importlib.metadata
import json
import platform
import time
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from wattscope.data import load_hourly
from wattscope.features import FEATURE_NAMES, build_examples
from wattscope.metrics import calibration_radii, prediction_intervals, regression_metrics
from wattscope.modeling import CONFIGURATIONS, fit_model, predict_model

INTERVAL_NOTE = (
    "Nominal 90% pointwise intervals, calibrated on held-out September residuals by horizon. "
    "Serial dependence and distribution shift mean 90% coverage is not guaranteed. "
    "These are not simultaneous 24-hour path intervals."
)


def save_plots(predictions: pd.DataFrame, report: dict, destination: Path) -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "axes.spines.top": False,
            "axes.spines.right": False,
            "figure.dpi": 150,
        }
    )
    sample = predictions.loc[
        (predictions.client == "MT_001") & (predictions.origin == pd.Timestamp("2014-12-15"))
    ]
    fig, axis = plt.subplots(figsize=(11, 4.5), layout="constrained")
    axis.fill_between(
        sample.target,
        sample.lower,
        sample.upper,
        alpha=0.15,
        color="#14b8a6",
        label="Nominal 90% calibrated interval",
    )
    axis.plot(sample.target, sample.actual, color="#172c42", lw=2, label="Observed")
    axis.plot(sample.target, sample.prediction, color="#0b9988", lw=2, label="Gradient boosting")
    axis.plot(sample.target, sample.previous_week, color="#9ca3af", ls="--", label="Previous week")
    axis.set(title="Day-ahead forecast · MT_001 · historical benchmark", ylabel="Hourly energy (kWh)")
    axis.legend(fontsize=8, loc="upper left")
    fig.autofmt_xdate()
    fig.savefig(destination / "forecast_example.png")
    plt.close(fig)
    by_horizon = predictions.groupby("horizon").apply(
        lambda group: pd.Series(
            {
                "model": (group.prediction - group.actual).abs().mean(),
                "day": (group.previous_day - group.actual).abs().mean(),
                "week": (group.previous_week - group.actual).abs().mean(),
            }
        ),
        include_groups=False,
    )
    fig, axis = plt.subplots(figsize=(10, 4), layout="constrained")
    for column, label, color in [
        ("model", "Gradient boosting", "#0b9988"),
        ("day", "Previous day", "#8b5cf6"),
        ("week", "Previous week", "#94a3b8"),
    ]:
        axis.plot(by_horizon.index, by_horizon[column], label=label, color=color)
    axis.set(title="Held-out Q4 2014 error by forecast horizon", xlabel="Hours ahead", ylabel="MAE (kWh)")
    axis.legend()
    fig.savefig(destination / "error_by_horizon.png")
    plt.close(fig)
    clients = report["per_client"]
    labels = [row["client_id"] for row in clients]
    fig, axis = plt.subplots(figsize=(11, 4.5), layout="constrained")
    positions = np.arange(len(labels))
    for offset, column, color, label in [
        (-0.25, "model", "#0b9988", "Gradient boosting"),
        (0, "previous_day", "#8b5cf6", "Previous day"),
        (0.25, "previous_week", "#94a3b8", "Previous week"),
    ]:
        axis.bar(
            positions + offset,
            [row[column]["wape"] or 0 for row in clients],
            width=0.25,
            color=color,
            label=label,
        )
    axis.set(
        xticks=positions,
        xticklabels=labels,
        ylabel="WAPE (%)",
        title="Performance varies by client · held-out Q4 2014",
    )
    axis.legend()
    fig.savefig(destination / "client_comparison.png")
    plt.close(fig)


def train(root: Path) -> dict:
    started = time.perf_counter()
    root = Path(root)
    frame = load_hourly(root)
    train_set = build_examples(frame, "2013-01-08", "2014-09-01")
    validation = build_examples(frame, "2014-09-01", "2014-09-15")
    selection = []
    for index, parameters in enumerate(CONFIGURATIONS):
        tick = time.perf_counter()
        print(f"Evaluating predefined configuration {index + 1}/{len(CONFIGURATIONS)}...", flush=True)
        candidate = fit_model(train_set, parameters)
        prediction = predict_model(candidate, validation.x, validation.scale)
        selection.append(
            {
                "configuration": parameters,
                "validation": regression_metrics(validation.y, prediction),
                "fit_seconds": round(time.perf_counter() - tick, 3),
            }
        )
    winner = min(selection, key=lambda item: item["validation"]["mae"])
    print("Refitting the selected configuration before the calibration window...", flush=True)
    refit = build_examples(frame, "2013-01-08", "2014-09-15")
    model = fit_model(refit, winner["configuration"])
    calibration = build_examples(frame, "2014-09-16", "2014-09-30")
    cal_prediction = predict_model(model, calibration.x, calibration.scale)
    radii = calibration_radii(calibration.y, cal_prediction, calibration.scale, calibration.horizon)
    # Model is now frozen. Test observations become history only AFTER their origin is reached.
    test = build_examples(frame, "2014-10-01", "2015-01-01")
    prediction = predict_model(model, test.x, test.scale)
    lower, upper = prediction_intervals(prediction, test.scale, test.horizon, radii)
    predictions = pd.DataFrame(
        {
            "origin": test.origin,
            "target": test.target,
            "client": test.client,
            "horizon": test.horizon,
            "actual": test.y,
            "prediction": prediction,
            "previous_day": test.previous_day,
            "previous_week": test.previous_week,
            "lower": lower,
            "upper": upper,
        }
    )
    scores = {
        "model": regression_metrics(test.y, prediction),
        "previous_day": regression_metrics(test.y, test.previous_day),
        "previous_week": regression_metrics(test.y, test.previous_week),
    }
    fold_metrics = []
    for month, group in predictions.groupby(predictions.origin.dt.to_period("M")):
        fold_metrics.append(
            {
                "period": str(month),
                "predictions": len(group),
                **{
                    name: regression_metrics(group.actual, group[column])
                    for name, column in [
                        ("model", "prediction"),
                        ("previous_day", "previous_day"),
                        ("previous_week", "previous_week"),
                    ]
                },
                "interval_coverage": float(
                    ((group.actual >= group.lower) & (group.actual <= group.upper)).mean()
                ),
            }
        )
    per_client = []
    for client_id, group in predictions.groupby("client"):
        per_client.append(
            {
                "client_id": client_id,
                **{
                    name: regression_metrics(group.actual, group[column])
                    for name, column in [
                        ("model", "prediction"),
                        ("previous_day", "previous_day"),
                        ("previous_week", "previous_week"),
                    ]
                },
                "interval_coverage": float(
                    ((group.actual >= group.lower) & (group.actual <= group.upper)).mean()
                ),
            }
        )
    metadata = json.loads((root / "data" / "metadata.json").read_text(encoding="utf-8"))
    report = {
        "project_name": "WattScope",
        "default_origin": "2014-12-15T00:00:00",
        "client_id_default": "MT_001",
        "data": {
            "source": metadata["source"],
            "unit": "kWh",
            "clients": len(frame.columns),
            "start": frame.index[0].isoformat(),
            "end": frame.index[-1].isoformat(),
            "train_start": "2013-01-08",
            "train_end": "2014-08-31",
            "validation_start": "2014-09-01",
            "validation_end": "2014-09-14",
            "calibration_start": "2014-09-16",
            "calibration_end": "2014-09-29",
            "test_start": "2014-10-01",
            "test_end": "2014-12-31",
        },
        "metrics": scores,
        "model": {
            "name": "Histogram gradient boosting",
            "features": FEATURE_NAMES,
            "configuration": winner["configuration"],
            "interval_note": INTERVAL_NOTE,
            "interval_coverage": float(((test.y >= lower) & (test.y <= upper)).mean()),
            "mean_interval_width_kwh": float(np.mean(upper - lower)),
            "nominal_pointwise_coverage": 0.9,
            "fit_through": "2014-09-15T00:00:00",
            "calibration_through": "2014-09-30T00:00:00",
            "forecast_start": "2014-10-01T00:00:00",
        },
        "validation": {
            "strategy": "Frozen model · daily rolling origins · held-out Q4 2014",
            "horizon_hours": 24,
            "train_examples": len(train_set.y),
            "refit_examples": len(refit.y),
            "selection_examples": len(validation.y),
            "calibration_examples": len(calibration.y),
            "test_examples": len(test.y),
            "selection_metric": "Validation MAE in original kWh units",
            "origin_clock": "Midnight in the original normalized Portuguese local clock",
        },
        "selection": selection,
        "folds": fold_metrics,
        "per_client": per_client,
        "macro_client_wape": {
            name: float(np.mean([row[name]["wape"] for row in per_client if row[name]["wape"] is not None]))
            for name in scores
        },
        "notes": metadata["source_caveats"]
        + [
            "Eight predetermined clients; results do not generalize to all 370 clients or unseen sites.",
            "Hyperparameters chosen on validation only; the fitted model is not changed after calibration.",
            "Actual historical observations update the feature history at each daily forecast origin.",
            "Pooled WAPE weights high-volume clients more heavily; per-client and macro scores are also reported.",
        ],
        "environment": {
            "python": platform.python_version(),
            **{
                name: importlib.metadata.version(name)
                for name in ["numpy", "pandas", "scikit-learn", "scipy", "joblib", "matplotlib"]
            },
        },
        "dataset_sha256": metadata["processed_sha256"],
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    reports = root / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (root / "models").mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "radii": radii,
            "clients": list(frame.columns),
            "fit_through": report["model"]["fit_through"],
            "calibration_through": report["model"]["calibration_through"],
            "forecast_start": report["model"]["forecast_start"],
            "feature_names": FEATURE_NAMES,
            "data_sha256": metadata["processed_sha256"],
            "sklearn_version": report["environment"]["scikit-learn"],
        },
        root / "models" / "model.joblib",
        compress=3,
    )
    predictions.to_csv(
        reports / "predictions.csv.gz",
        index=False,
        float_format="%.8f",
        compression={"method": "gzip", "mtime": 0},
    )
    (reports / "results.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    save_plots(predictions, report, reports)
    write_report(report, reports / "EXPERIMENT_REPORT.md")
    print(json.dumps(scores, indent=2), flush=True)
    return report


def write_report(report: dict, path: Path) -> None:
    lines = [
        "# WattScope experiment report",
        "",
        "Generated from a completed run; no hand-entered performance claims.",
        "",
        "## Protocol",
        "",
        "- Data: original UCI electricity readings; fixed first eight clients; hourly kWh.",
        "- Train origins: 8 January 2013–31 August 2014.",
        "- Hyperparameter selection origins: 1–14 September 2014; minimum validation MAE.",
        "- Final model fit uses origins through 14 September (labels through 15 September 00:00).",
        "- Calibration origins: 16–29 September 2014. No subsequent refit.",
        "- Held-out test: daily midnight origins in October, November and December 2014, 24 hours per origin.",
        "- Earlier test observations may enter later forecast histories, but never model fitting.",
        "",
        "## Held-out results",
        "",
        "| Method | MAE (kWh) | RMSE (kWh) | WAPE (%) |",
        "| --- | ---: | ---: | ---: |",
    ]
    for name, label in [
        ("model", "Histogram gradient boosting"),
        ("previous_day", "Previous-day seasonal naive"),
        ("previous_week", "Previous-week seasonal naive"),
    ]:
        score = report["metrics"][name]
        lines.append(f"| {label} | {score['mae']:.4f} | {score['rmse']:.4f} | {score['wape']:.2f} |")
    lines += [
        "",
        "MAE = mean absolute error. RMSE = root mean squared error. "
        "WAPE = 100 × sum(abs(error)) / sum(abs(actual)).",
        "Pooled errors weight clients by their load magnitude. Macro-client WAPE and each client's "
        "results are available in `results.json`.",
        "",
        "## Monthly test folds",
        "",
        "| Origin month | Model WAPE (%) | Previous-day WAPE (%) | Previous-week WAPE (%) | Interval coverage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for fold in report["folds"]:
        lines.append(
            f"| {fold['period']} | {fold['model']['wape']:.2f} | {fold['previous_day']['wape']:.2f} | "
            f"{fold['previous_week']['wape']:.2f} | {fold['interval_coverage']:.1%} |"
        )
    lines += [
        "",
        "## Prediction intervals",
        "",
        INTERVAL_NOTE,
        f"Observed test coverage: **{report['model']['interval_coverage']:.1%}**. "
        f"Mean interval width: **{report['model']['mean_interval_width_kwh']:.4f} kWh**.",
        "Calibration uses horizon-specific finite-sample quantiles of absolute residuals normalized "
        "by the trailing seven-day mean. Lower endpoints are clipped at zero.",
        "",
        "## Limitations",
        "",
        *[f"- {note}" for note in report["notes"]],
        "- This is a historical benchmark, not a live energy feed or a commercial deployment.",
        "- Three predefined parameter configurations constitute a small search, not an exhaustive optimizer.",
        "- The source does not identify household types, location-specific weather or tariffs; none are inferred.",
        "",
        "## Reproducibility",
        "",
        "Run `python -m wattscope.cli train` from the repository root.",
        f"Processed data SHA-256: `{report['dataset_sha256']}`.",
        "Environment: "
        + ", ".join(f"{name} {version}" for name, version in report["environment"].items())
        + ".",
        "Exact predictions, parameter selection and evaluation slices are saved alongside this report.",
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
