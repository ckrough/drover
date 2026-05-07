"""Generate static PNG charts from eval/dashboard_data.json.

Produces two artifacts in eval/charts/:

- ocr-mac-deltas.png — grouped bar chart contrasting the most recent
  rapidocr-baseline run with the most recent ocrmac run on the synthetic
  corpus, across the five accuracy metrics.
- accuracy-over-time.png — line chart of every metric for every run on
  the synthetic and real-world corpora, in chronological order.

Idempotent: rerunning regenerates the PNGs from the current
dashboard_data.json. Charts are committed to the repo; the script only
needs to run when new evaluation runs are added.

Usage:
    uv run python scripts/build_eval_charts.py
"""

from __future__ import annotations

import json
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

OCR_BASELINE_RUN_ID = "ocr-baseline-rapidocr-20260507-100620-gemma4_docling"
OCR_MAC_RUN_ID = "ocr-mac-20260507-110208-gemma4_docling"


def _load_runs() -> list[dict[str, Any]]:
    with DASHBOARD_DATA.open() as f:
        data = json.load(f)
    return data["runs"]


def _find_run(runs: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    for r in runs:
        if r["run_id"] == run_id:
            return r
    raise KeyError(f"run not found: {run_id}")


def _to_pct(values: list[float]) -> list[float]:
    return [v * 100 for v in values]


def render_ocr_deltas(runs: list[dict[str, Any]], out_path: Path) -> None:
    """Grouped bar chart: rapidocr baseline vs ocrmac across the five metrics."""
    baseline = _find_run(runs, OCR_BASELINE_RUN_ID)
    candidate = _find_run(runs, OCR_MAC_RUN_ID)

    baseline_vals = _to_pct([baseline[k] for k in METRIC_KEYS])
    candidate_vals = _to_pct([candidate[k] for k in METRIC_KEYS])

    x = range(len(METRIC_LABELS))
    width = 0.38

    fig, ax = plt.subplots(figsize=(9, 5))
    bars_a = ax.bar(
        [i - width / 2 for i in x],
        baseline_vals,
        width,
        label="Baseline: rapidocr + torch CPU",
        color="#9aa0a6",
    )
    bars_b = ax.bar(
        [i + width / 2 for i in x],
        candidate_vals,
        width,
        label="ocr-mac: ocrmac (Apple Vision)",
        color="#1a73e8",
    )

    ax.set_ylabel("Accuracy (%)")
    ax.set_title(
        "OCR backend impact on classification accuracy\n"
        f"{baseline['model']} on {baseline['corpus']} corpus "
        f"(n={baseline['corpus_size']})"
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(METRIC_LABELS)
    ax.set_ylim(0, 105)
    ax.grid(axis="y", linestyle="--", alpha=0.4)
    ax.legend(loc="lower right")

    for bar_group in (bars_a, bars_b):
        for bar in bar_group:
            height = bar.get_height()
            ax.annotate(
                f"{height:.1f}",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=9,
            )

    fig.tight_layout()
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def render_accuracy_over_time(runs: list[dict[str, Any]], out_path: Path) -> None:
    """Line chart: each metric across runs, faceted by corpus."""
    by_corpus: dict[str, list[dict[str, Any]]] = {}
    for r in runs:
        by_corpus.setdefault(r["corpus"], []).append(r)
    for corpus_runs in by_corpus.values():
        corpus_runs.sort(key=lambda r: (r["date"], r["run_id"]))

    corpora = sorted(by_corpus.keys())
    fig, axes = plt.subplots(
        len(corpora), 1, figsize=(11, 4.2 * len(corpora)), sharex=False
    )
    if len(corpora) == 1:
        axes = [axes]

    for ax, corpus in zip(axes, corpora):
        corpus_runs = by_corpus[corpus]
        labels = [_short_label(r) for r in corpus_runs]
        x = range(len(corpus_runs))

        for metric_key, metric_label in zip(METRIC_KEYS, METRIC_LABELS):
            values = _to_pct([r.get(metric_key) or 0.0 for r in corpus_runs])
            ax.plot(
                x, values, marker="o", linewidth=1.6, label=metric_label
            )

        ax.set_title(f"{corpus.capitalize()} corpus")
        ax.set_ylabel("Accuracy (%)")
        ax.set_ylim(0, 105)
        ax.set_xticks(list(x))
        ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=8)
        ax.grid(axis="y", linestyle="--", alpha=0.4)
        ax.legend(loc="lower right", fontsize=8, ncol=5)

    fig.suptitle("Classification accuracy over time, by metric and corpus", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    fig.savefig(out_path, dpi=140)
    plt.close(fig)


def _short_label(run: dict[str, Any]) -> str:
    """Compact x-axis label: date + a hint about the run variant."""
    date = run["date"]
    rid = run["run_id"]
    hint = ""
    if "ocr-baseline" in rid:
        hint = " rapidocr"
    elif "ocr-mac" in rid:
        hint = " ocrmac"
    elif "unstructured" in rid:
        hint = " unstr"
    elif "picture-ocr" in rid:
        hint = " pic-ocr"
    elif "post-audit" in rid:
        hint = " post-audit"
    elif "structured" in rid:
        hint = " structured"
    elif "parity" in rid:
        hint = " parity"
    return f"{date}{hint}".strip()


def main() -> None:
    CHARTS_DIR.mkdir(parents=True, exist_ok=True)
    runs = _load_runs()
    render_ocr_deltas(runs, CHARTS_DIR / "ocr-mac-deltas.png")
    render_accuracy_over_time(runs, CHARTS_DIR / "accuracy-over-time.png")
    print(f"Wrote {CHARTS_DIR / 'ocr-mac-deltas.png'}")
    print(f"Wrote {CHARTS_DIR / 'accuracy-over-time.png'}")


if __name__ == "__main__":
    main()
