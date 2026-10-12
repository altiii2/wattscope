# Reproducibility checklist

Use this checklist to verify a fresh environment and review experiment artifacts before publishing a release.

## Environment and data

- [ ] Install Python 3.12 and the versions in `requirements.lock`.
- [ ] Follow the README to install the package and start the API.
- [ ] Check the source attribution and dataset license in `data/metadata.json`.
- [ ] Verify file checksums against `SHA256SUMS.txt`.
- [ ] Confirm the target unit, hourly aggregation, incomplete-hour handling and 24-hour forecast contract.
- [ ] Record any changes to the selected clients or preprocessing assumptions.

## Experiment

- [ ] Keep training, validation, calibration and test periods chronological and separate.
- [ ] Check that measurement features use only observations available at the forecast origin.
- [ ] Compare all models on the same eligible observations.
- [ ] Select model settings using validation data and freeze the predictor before calibration.
- [ ] Reproduce MAE, WAPE, interval coverage and interval width from the saved predictions.
- [ ] Inspect results by client, forecast horizon and month, alongside pooled scores.
- [ ] Record the configuration and observed results of any additional experiments, including weaker results.

## Serving and documentation

- [ ] Run `pytest -q` and `ruff check .`.
- [ ] Verify that the API uses the same model artifact and feature code as the experiment.
- [ ] Exercise a supported forecast origin and inspect timestamps, units and interval labels.
- [ ] Check the responses for an unknown client, an invalid origin and missing artifacts.
- [ ] Confirm that screenshots and API examples match the current implementation.
- [ ] Keep the historical-data scope and known limitations visible in the documentation.
- [ ] Link reported results to their configuration, predictions and validation evidence.

## References

- [Technical walkthrough](LEARNING_GUIDE.md)
- [Model card](MODEL_CARD.md)
- [Validation record](VALIDATION.md)
- [Experiment report](../reports/EXPERIMENT_REPORT.md)

The source code and documentation use the MIT license. The UCI dataset and processed subset retain their CC BY 4.0 attribution requirements.
