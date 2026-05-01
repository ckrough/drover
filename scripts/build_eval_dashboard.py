"""Build eval/dashboard_data.json and update the inline data block in eval/dashboard.html.

Idempotent: existing entries with the same run_id are preserved. New runs
found in eval/runs/ that are not already recorded are appended. Runs are
sorted chronologically by date then run_id.

Usage:
    uv run python scripts/build_eval_dashboard.py

The script strips all per-document records and filenames from the raw JSON
dumps before writing to dashboard_data.json. Only aggregate metrics are
committed to the summary file.

After updating dashboard_data.json, the script also rewrites the inline
<script id="data" type="application/json"> block in dashboard.html so both
files stay in sync. This keeps the dashboard loadable via file:// without
a local server.
"""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
EVAL_DIR = REPO_ROOT / "eval"
RUNS_DIR = EVAL_DIR / "runs"
DASHBOARD_DATA = EVAL_DIR / "dashboard_data.json"
DASHBOARD_HTML = EVAL_DIR / "dashboard.html"

SCHEMA_VERSION = 1

# ---------------------------------------------------------------------------
# Keys that are safe to commit (no per-doc records, no filenames)
# ---------------------------------------------------------------------------

_METRIC_KEYS = (
    "domain_accuracy",
    "category_accuracy",
    "doctype_accuracy",
    "vendor_accuracy",
    "date_accuracy",
)

_AGGREGATE_KEYS: set[str] = {
    *_METRIC_KEYS,
    "model",
    "provider",
    "total",
    "errors",
}


def _extract_aggregate(raw: dict[str, Any]) -> dict[str, Any]:
    """Return only aggregate (non-per-doc) fields from a raw JSON dump."""
    return {k: v for k, v in raw.items() if k in _AGGREGATE_KEYS}


def _rfc3339_now() -> str:
    """Return current time as an RFC 3339 string (local timezone)."""
    result = subprocess.run(
        ["date", "-Iseconds"], capture_output=True, text=True, check=True
    )
    return result.stdout.strip()


def _infer_loader_from_filename(fname: str) -> str:
    """Infer loader name from JSON filename convention (e.g. gemma4_docling.json)."""
    stem = Path(fname).stem
    parts = stem.split("_")
    if parts and parts[-1] in ("docling", "unstructured"):
        return parts[-1]
    return "unknown"


def _infer_corpus_from_dir(dir_name: str) -> str:
    """Infer corpus label from run directory name."""
    if "real-world" in dir_name or "post-audit" in dir_name:
        return "real-world"
    return "synthetic"


def _parse_date_from_dir(dir_name: str) -> str:
    """Extract YYYY-MM-DD from a directory name."""
    match = re.search(r"(\d{4}-\d{2}-\d{2})", dir_name)
    if match:
        return match.group(1)
    return "unknown"


def _loader_variant_from_dir(dir_name: str) -> str | None:
    """Return a loader_variant label if the dir name implies one."""
    if "picture-ocr" in dir_name:
        return "picture-region-ocr"
    if "structured" in dir_name and "real-world" in dir_name:
        return "structured-regions"
    if "post-audit" in dir_name:
        return "full-page-ocr"
    return None


def _load_existing() -> dict[str, Any]:
    """Load existing dashboard_data.json or return a fresh skeleton."""
    if DASHBOARD_DATA.exists():
        with DASHBOARD_DATA.open() as f:
            data: dict[str, Any] = json.load(f)
            return data
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _rfc3339_now(),
        "runs": [],
    }


def _existing_run_ids(data: dict[str, Any]) -> set[str]:
    return {r["run_id"] for r in data.get("runs", [])}


# ---------------------------------------------------------------------------
# Scanning
# ---------------------------------------------------------------------------


def _make_run_id(dir_name: str, json_stem: str) -> str:
    """Construct a stable run_id from directory and json stem."""
    if dir_name == "__root__":
        return f"legacy-{json_stem}"
    return f"{dir_name}-{json_stem}"


def scan_runs_dir(
    existing_ids: set[str],
) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    """Scan eval/runs/ for JSON run dumps.

    Returns:
        new_runs: list of run dicts to add.
        added_ids: list of run_ids that were added.
        skipped: list of items that were skipped (with reason).
    """
    new_runs: list[dict[str, Any]] = []
    added_ids: list[str] = []
    skipped: list[str] = []

    if not RUNS_DIR.exists():
        print(f"[warn] {RUNS_DIR} does not exist, skipping scan.")
        return new_runs, added_ids, skipped

    # Collect (dir_label, dir_path_or_None, json_file) tuples
    items: list[tuple[str, Path | None, Path]] = []

    for item in sorted(RUNS_DIR.iterdir()):
        if item.is_file() and item.suffix == ".json":
            items.append(("__root__", None, item))
        elif item.is_dir():
            for jf in sorted(item.glob("*.json")):
                items.append((item.name, item, jf))

    for dir_label, _dir_path, jf in items:
        stem = jf.stem
        run_id = _make_run_id(dir_label, stem)

        if run_id in existing_ids:
            skipped.append(f"{run_id} (already recorded)")
            continue

        try:
            with jf.open() as f:
                raw = json.load(f)
        except (json.JSONDecodeError, OSError) as exc:
            skipped.append(f"{run_id} (read error: {exc})")
            continue

        agg = _extract_aggregate(raw)
        if not any(agg.get(k) is not None for k in _METRIC_KEYS):
            skipped.append(f"{run_id} (no metric keys)")
            continue

        loader = _infer_loader_from_filename(jf.name)
        loader_variant = (
            _loader_variant_from_dir(dir_label) if dir_label != "__root__" else None
        )
        date_str = (
            _parse_date_from_dir(dir_label) if dir_label != "__root__" else "unknown"
        )
        corpus = (
            _infer_corpus_from_dir(dir_label)
            if dir_label != "__root__"
            else "synthetic"
        )

        run: dict[str, Any] = {
            "run_id": run_id,
            "date": date_str,
            "corpus": corpus,
            "corpus_size": agg.get("total"),
            "model": agg.get("model", "unknown"),
            "provider": agg.get("provider", "unknown"),
            "loader": loader,
            **{k: agg[k] for k in _METRIC_KEYS if k in agg},
            "errors": agg.get("errors", 0),
            "source": (
                f"eval/runs/{jf.name}"
                if dir_label == "__root__"
                else f"eval/runs/{dir_label}/{jf.name}"
            ),
            "notes": (
                "Legacy root-level run (date unknown)."
                if dir_label == "__root__"
                else ""
            ),
        }
        if loader_variant:
            run["loader_variant"] = loader_variant

        new_runs.append(run)
        added_ids.append(run_id)

    return new_runs, added_ids, skipped


# ---------------------------------------------------------------------------
# Sorting
# ---------------------------------------------------------------------------


def _sort_key(run: dict[str, Any]) -> tuple[str, str]:
    date = run.get("date", "unknown")
    # Put "unknown" dates at the start so they don't pollute the tail
    if date in ("unknown", ""):
        date = "0000-00-00"
    return (date, run.get("run_id", ""))


# ---------------------------------------------------------------------------
# HTML inline-data sync
# ---------------------------------------------------------------------------

_HTML_DATA_OPEN = '<script id="data" type="application/json">'
_HTML_DATA_CLOSE = "</script>"


def update_html_data_block(html_path: Path, json_text: str) -> None:
    """Replace the inline JSON data block in dashboard.html with *json_text*.

    Finds the ``<script id="data" type="application/json">`` marker, replaces
    everything between it and the next ``</script>`` with *json_text*, and
    writes the file back. The function is idempotent: running it twice with
    the same JSON produces no further changes.

    Args:
        html_path: Path to dashboard.html.
        json_text: Serialised JSON string to embed (should end with a newline).

    Raises:
        ValueError: If the expected markers are not found in the HTML.
        OSError: On file read/write failure.
    """
    html = html_path.read_text(encoding="utf-8")

    open_idx = html.find(_HTML_DATA_OPEN)
    if open_idx == -1:
        raise ValueError(
            f"Marker '{_HTML_DATA_OPEN}' not found in {html_path}. "
            "Cannot update inline data block."
        )

    # Search for closing tag after the opening marker
    after_open = open_idx + len(_HTML_DATA_OPEN)
    close_idx = html.find(_HTML_DATA_CLOSE, after_open)
    if close_idx == -1:
        raise ValueError(
            f"Closing '{_HTML_DATA_CLOSE}' not found after data marker in {html_path}."
        )

    updated = html[:after_open] + "\n" + json_text + html[close_idx:]
    html_path.write_text(updated, encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    """Entry point: scan runs dir, merge with existing data, write output."""
    print(f"Loading existing data from {DASHBOARD_DATA}")
    data = _load_existing()
    existing_ids = _existing_run_ids(data)
    print(f"  Found {len(existing_ids)} existing run(s).")

    new_runs, added_ids, skipped = scan_runs_dir(existing_ids)

    if new_runs:
        data["runs"].extend(new_runs)
        print(f"\nAdded {len(added_ids)} new run(s):")
        for rid in added_ids:
            print(f"  + {rid}")
    else:
        print("\nNo new runs found.")

    if skipped:
        print(f"\nSkipped {len(skipped)} item(s):")
        for s in skipped:
            print(f"  - {s}")

    # Sort all runs chronologically
    data["runs"].sort(key=_sort_key)
    data["generated_at"] = _rfc3339_now()
    data["schema_version"] = SCHEMA_VERSION

    json_text = json.dumps(data, indent=2) + "\n"

    with DASHBOARD_DATA.open("w") as f:
        f.write(json_text)

    print(f"\nWrote {len(data['runs'])} total run(s) to {DASHBOARD_DATA}")

    if DASHBOARD_HTML.exists():
        update_html_data_block(DASHBOARD_HTML, json_text)
        print(f"Updated inline data block in {DASHBOARD_HTML}")
    else:
        print(f"[warn] {DASHBOARD_HTML} not found; skipping HTML update.")


if __name__ == "__main__":
    main()
