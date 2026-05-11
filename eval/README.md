# Drover Evaluation Suite

Ground-truth corpora, run logs, accuracy dashboard, and chart artifacts for benchmarking drover's classifier.

## Accuracy over time

Synthetic-corpus runs from the most recent baseline forward, in chronological order, with each accuracy metric as its own line. The leftmost point is the current baseline; subsequent points are changes from that baseline. Use this view to spot regressions across loader, taxonomy, or OCR-backend changes. X-axis labels are short commit hashes, matching the interactive dashboard.

![Classification accuracy from baseline forward, by metric (synthetic corpus)](charts/accuracy-over-time.png)

The interactive equivalent lives in [dashboard.html](dashboard.html); load it locally (file:// works, no server needed) for tooltips, per-doc runtime, and run-level metadata.

To re-establish the baseline, run a fresh evaluation into a directory named `eval/runs/baseline-<YYYYMMDD-HHMMSS>/`. `scripts/build_eval_dashboard.py` tags that run with `baseline: true`, and `scripts/build_eval_charts.py` clips the static chart to start at that run.

## Reproducing

Both charts and the dashboard are derived from `dashboard_data.json`, which itself is built from the per-run `*.json` files (gitignored) under `runs/`. After adding a new run:

```bash
uv run python scripts/build_eval_dashboard.py   # updates dashboard.html + dashboard_data.json
uv run python scripts/build_eval_charts.py      # updates charts/*.png
```

Both scripts are idempotent.
