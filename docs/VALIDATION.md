# Validation

Validation was performed on Windows with Python 3.12.14 and the exact versions in `requirements.lock`.

## Completed

- Original UCI archive downloaded and its SHA-256 recorded in `data/metadata.json`.
- Original quarter-hour readings parsed; fixed first eight clients converted to 17,521 hourly rows.
- All three predeclared model configurations evaluated on the validation window.
- Selected model refitted before a separate calibration window, then frozen for 17,664 Q4 test predictions.
- Metrics, interval coverage, monthly folds, per-client scores and figures generated from actual predictions.
- **27 tests passed**, covering quarter-hour energy conversion, partial hours, future-data invariance, seasonal lag alignment, invalid histories, WAPE, calibration quantiles, API validation, missing artifacts, actual model inference and an audit of the reported metrics.
- Ruff lint and formatting checks passed; JavaScript syntax check passed.
- Editable package installation completed successfully.
- Local HTTP server and English dashboard exercised with the trained artifact. Client switching, default-window reset and rendered metrics were checked in the browser.
- Browser console contained no warnings or errors in the verified session.
- Desktop and narrow in-app rendering were inspected; the screenshot is stored in `reports/dashboard.jpg`.

## Method review correction

Inference is allowed only from 1 October 2014 onward, after both fitting and calibration. Earlier origins would otherwise expose interval widths calibrated using outcomes that had not yet occurred at those origins. The regression tests reject an origin inside the calibration period. This correction does not change the clean Q4 benchmark results.

## Hosted validation

On 12 October 2026, [GitHub Actions run 38258258551](https://github.com/altiii2/wattscope/actions/runs/38258258551) completed successfully on Ubuntu with Python 3.12 at commit `ec0a6b97f6928e09a81ef0d5e3d279ad352525d3`. The run installed the locked dependencies and editable package, then passed `ruff check .` and `pytest -q`.

## Not executed locally

- Docker build/run: Docker is not installed on the validation host. The recipe is supplied, not claimed as tested.
- Cloud deployment, uptime testing and operational integration with live energy meters.

## Development dependency note

The test client emitted a Starlette deprecation warning about its current `httpx` compatibility path. Tests completed successfully. This is recorded rather than suppressing the warning.

## Re-run

```bash
pytest -q
ruff check .
ruff format --check .
node --check src/wattscope/static/app.js
```

Tests that inspect the trained artifact are skipped if the artifact has deliberately been removed. Training from the supplied data recreates it.
