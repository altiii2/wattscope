# WattScope portfolio checklist

Use this checklist before sharing WattScope in a portfolio, interview, or application. Describe the work you actually did and the results you can reproduce.

## Make the project reproducible

- [ ] The README explains setup, data preparation, training, evaluation, API startup, and the dashboard.
- [ ] The original UCI source is credited, and data access and redistribution follow the dataset's terms.
- [ ] The target column, unit, hourly aggregation, missing-data handling, and 24-hour forecast contract are documented.
- [ ] Training, validation, calibration, and test dates are explicit and chronological.
- [ ] Learned preprocessing uses only the permitted fitting period; features use only information available at the forecast origin.
- [ ] A fresh run creates the artifacts needed to reproduce every reported number.
- [ ] The same eligible observations are used when comparing the learned model with daily and weekly seasonal baselines.
- [ ] Reports give actual test MAE, WAPE, interval coverage, and interval width with units and evaluation context.
- [ ] Any failed run, weak result, or important limitation is described accurately.
- [ ] API examples and dashboard screenshots match the current code and label the data as a historical demo.

Do not fill in attractive performance numbers as placeholders. If no evaluation has been run, say “not yet measured.” If the model does not outperform a baseline, report that outcome and explain what you learned.

## Record your own contributions

Keep a short contribution log while working. For each meaningful change, record:

| Field | What to record |
| --- | --- |
| Date and change | A concrete task, linked to the relevant commit or file. |
| Your contribution | What you designed, wrote, modified, investigated, or verified yourself. |
| Decision | Why you accepted, changed, or rejected a suggested approach. |
| Verification | The command, check, report, or manual review you used and its actual outcome. |
| Remaining gap | What you cannot yet explain or reproduce. |

Write specific entries such as “checked that lag features use observations available at the forecast origin” only after doing that check.

## Protect private information in public artifacts

- [ ] The repository contains no API keys, passwords, tokens, or credentials.
- [ ] Logs, notebooks, screenshots, and example payloads contain no private contacts, personal email exchanges, or other people's personal information.
- [ ] You have permission to publish any materials contributed by others.
- [ ] Author names and affiliations are accurate; placeholders are removed instead of replaced with invented details.

The MIT license applies to the repository's own code and documentation. External data, libraries, and borrowed materials retain their respective terms; the repository license does not override them.

## Prepare a short, defensible explanation

Be ready to explain:

- The problem, target unit, and intended forecast decision.
- Why the seasonal baselines are credible comparisons.
- How the chronological split and feature timing prevent leakage.
- What the actual evaluation says, including where the model struggles.
- How intervals are calibrated and what their coverage means.
- Which work is yours and what you would improve next.

Link to evidence for each result: a reproducible command, report, relevant code, or documented contribution. A portfolio project may support an application, but it provides no admission, scholarship, interview, or employment guarantee.
