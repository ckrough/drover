"""Generate static PNG charts from eval/dashboard_data.json.

Produces eval/charts/accuracy-over-time.png — a line chart of every
metric for every run, in chronological order.

The dashboard policy in `build_eval_dashboard.py` keeps only synthetic-
corpus runs that have both a runtime_seconds and a corpus_size, so the
chart inherits that filter automatically.

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


def _load_runs() -> list[dict[str, Any]]:
    with DASHBOARD_DATA.open() as f:
        data: dict[str, Any] = json.load(f)
    runs: list[dict[str, Any]] = data["runs"]
    return runs


def _to_pct(values: list[float]) -> list[float]:
    return [v * 100 for v in values]


def render_accuracy_over_time(runs: list[dict[str, Any]], out_path: Path) -> None:
    """Line chart: each metric across runs, oldest to newest."""
    runs = sorted(runs, key=lambda r: (r["date"], r["run_id"]))

    fig, ax = plt.subplots(figsize=(11, 4.5))
    labels = [_short_label(r) for r in runs]
    x = range(len(runs))

    for metric_key, metric_label in zip(METRIC_KEYS, METRIC_LABELS, strict=True):
        values = _to_pct([r.get(metric_key) or 0.0 for r in runs])
        ax.plot(x, values, marker="o", linewidth=1.6, label=metric_label)

    ax.set_ylabel("Accuracy (%)")
    ax.set_ylim(0, 105)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="lower right", fontsize=8, ncol=5)

    fig.suptitle(
        "Classification accuracy over time, by metric (synthetic corpus)",
        fontsize=12,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


_RUN_TS_RE = re.compile(
    r"(?P<y>\d{4})-?(?P<m>\d{2})-?(?P<d>\d{2})[-T](?P<H>\d{2})(?P<M>\d{2})"
)


def _short_label(run: dict[str, Any]) -> str:
    """Compact x-axis label: date + HH:MM (when run_id encodes a timestamp).

    Including the time keeps labels unique for runs that share a date, which
    matches the interactive dashboard's behavior.
    """
    date = run["date"]
    rid = run.get("run_id", "")
    match = _RUN_TS_RE.search(rid)
    time_suffix = f" {match.group('H')}:{match.group('M')}" if match else ""
    return f"{date}{time_suffix}"


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    runs = _load_runs()
    render_accuracy_over_time(runs, CHARTS_DIR / "accuracy-over-time.png")
    print(f"Wrote {CHARTS_DIR / 'accuracy-over-time.png'}")


if __name__ == "__main__":
    main()
