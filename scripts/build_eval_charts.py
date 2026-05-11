"""Generate static PNG charts from eval/dashboard_data.json.

Produces eval/charts/accuracy-over-time.png — a line chart of every
metric for each run from the most-recent baseline forward, in
chronological order. Runs are tagged as baseline by
`build_eval_dashboard.py` when their directory name starts with
`baseline-`; the chart filters to runs at-or-after the most recent
baseline so the leftmost point is always the current reference run.

The dashboard policy in `build_eval_dashboard.py` keeps only synthetic-
corpus runs that have both a runtime_seconds and a corpus_size, so the
chart inherits that filter automatically.

X-axis labels are short commit hashes, matching the interactive
dashboard's `fmtCommit`. Runs without a captured commit hash fall back
to their run_id.

Idempotent: rerunning regenerates the PNG from the current
dashboard_data.json. Charts are committed to the repo; the script only
needs to run when new evaluation runs are added.

Usage:
    uv run python scripts/build_eval_charts.py
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt

REPO_ROOT = Path(__file__).parent.parent
EVAL_DIR = REPO_ROOT / "eval"
DASHBOARD_DATA = EVAL_DIR / "dashboard_data.json"
CHARTS_DIR = EVAL_DIR / "charts"

METRIC_KEYS = (
    "domain_accuracy",
    "category_accuracy",
    "doctype_accuracy",
    "vendor_accuracy",
    "date_accuracy",
)
METRIC_LABELS = ("Domain", "Category", "Doctype", "Vendor", "Date")

_RUN_TS_RE = re.compile(r"(\d{8}-\d{6})")


def _load_runs() -> list[dict[str, Any]]:
    with DASHBOARD_DATA.open() as f:
        data: dict[str, Any] = json.load(f)
    runs: list[dict[str, Any]] = data["runs"]
    return runs


def _to_pct(values: list[float]) -> list[float]:
    return [v * 100 for v in values]


def _chrono_key(run: dict[str, Any]) -> tuple[str, str]:
    """Chronological sort key: prefer YYYYMMDD-HHMMSS embedded in run_id.

    Falls back to (date, run_id) so runs without a parseable timestamp still
    sort deterministically.
    """
    rid = run.get("run_id", "")
    match = _RUN_TS_RE.search(rid)
    if match:
        return (match.group(1), rid)
    return (run.get("date", ""), rid)


def _runs_from_baseline(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return runs at-or-after the most recent baseline, oldest to newest.

    Falls back to the full sorted list when no run is marked baseline, so
    the script remains usable in repos that have not yet established one.
    """
    ordered = sorted(runs, key=_chrono_key)
    baseline_idx = None
    for idx, run in enumerate(ordered):
        if run.get("baseline"):
            baseline_idx = idx
    if baseline_idx is None:
        return ordered
    return ordered[baseline_idx:]


def _short_commit(run: dict[str, Any]) -> str:
    """Short commit hash (7 char), matching the dashboard's fmtCommit."""
    commit = run.get("commit_hash")
    if isinstance(commit, str) and commit:
        return commit[:7]
    return str(run.get("run_id", ""))


def render_accuracy_over_time(runs: list[dict[str, Any]], out_path: Path) -> None:
    """Line chart: each metric across runs, oldest to newest, baseline first."""
    runs = _runs_from_baseline(runs)

    fig, ax = plt.subplots(figsize=(11, 4.5))
    labels = [_short_commit(r) for r in runs]
    x = range(len(runs))

    for metric_key, metric_label in zip(METRIC_KEYS, METRIC_LABELS, strict=True):
        values = _to_pct([r.get(metric_key) or 0.0 for r in runs])
        ax.plot(x, values, marker="o", linewidth=1.6, label=metric_label)

    ax.set_ylabel("Accuracy (%)")
    ax.set_xlabel("Commit")
    ax.set_ylim(0, 105)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="lower right", fontsize=8, ncol=5)

    fig.suptitle(
        "Classification accuracy from baseline forward, by metric (synthetic corpus)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    runs = _load_runs()
    render_accuracy_over_time(runs, CHARTS_DIR / "accuracy-over-time.png")
    print(f"Wrote {CHARTS_DIR / 'accuracy-over-time.png'}")


if __name__ == "__main__":
    main()
