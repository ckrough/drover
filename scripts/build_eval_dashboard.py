"""Build eval/dashboard_data.json and update the inline data block in eval/dashboard.html.

Idempotent: existing entries with the same run_id are preserved. New runs
found in eval/runs/ that are not already recorded are appended. Runs are
sorted chronologically by date then run_id.

Usage:
    uv run python scripts/build_eval_dashboard.py

The script strips all per-document records and filenames from the raw JSON
dumps before writing to dashboard_data.json. Only aggregate metrics are
committed to the summary file.

Runs whose directory name does not encode a parseable date are excluded
from the dashboard. Per-run runtime is computed from the first and last
timestamp in the run's `.stderr` file when present; commit hashes are
included only when the run JSON records one.

After updating dashboard_data.json, the script also rewrites the inline
<script id="data" type="application/json"> block in dashboard.html so both
files stay in sync. This keeps the dashboard loadable via file:// without
a local server.
"""

from __future__ import annotations

import json
import re
import subprocess  # nosec B404 - fixed-argv invocations only
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).parent.parent
EVAL_DIR = REPO_ROOT / "eval"
RUNS_DIR = EVAL_DIR / "runs"
DASHBOARD_DATA = EVAL_DIR / "dashboard_data.json"
DASHBOARD_HTML = EVAL_DIR / "dashboard.html"

SCHEMA_VERSION = 2

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
    "commit_hash",
    "commit",
    "runtime_seconds",
    "wallclock_s",
}

_DATE_PATTERNS = (
    re.compile(r"(\d{4}-\d{2}-\d{2})"),
    re.compile(r"(\d{4})(\d{2})(\d{2})"),
)

_STDERR_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2}) (\d{2}):(\d{2}):(\d{2})")


def _extract_aggregate(raw: dict[str, Any]) -> dict[str, Any]:
    """Return only aggregate (non-per-doc) fields from a raw JSON dump."""
    return {k: v for k, v in raw.items() if k in _AGGREGATE_KEYS}


def _rfc3339_now() -> str:
    """Return current time as an RFC 3339 string (local timezone)."""
    result = subprocess.run(  # nosec B603 B607 - fixed argv, no shell, trusted PATH
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
    if "real-world" in dir_name or "post-audit" in dir_name or "realworld" in dir_name:
        return "real-world"
    return "synthetic"


def _parse_date_from_dir(dir_name: str) -> str:
    """Extract YYYY-MM-DD from a directory name, supporting hyphenated and YYYYMMDD forms."""
    match = _DATE_PATTERNS[0].search(dir_name)
    if match:
        return match.group(1)
    match = _DATE_PATTERNS[1].search(dir_name)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
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


def _seconds_between(first: str, last: str) -> int | None:
    """Compute integer seconds between two `YYYY-MM-DD HH:MM:SS` strings on the same day."""
    fm = _STDERR_TS_RE.search(first)
    lm = _STDERR_TS_RE.search(last)
    if not fm or not lm:
        return None
    f_secs = int(fm.group(2)) * 3600 + int(fm.group(3)) * 60 + int(fm.group(4))
    l_secs = int(lm.group(2)) * 3600 + int(lm.group(3)) * 60 + int(lm.group(4))
    delta = l_secs - f_secs
    if fm.group(1) != lm.group(1):
        delta += 24 * 3600
    return delta if delta > 0 else None


def _runtime_from_stderr(json_path: Path) -> int | None:
    """Read the run's `.stderr` neighbour and return wallclock seconds, or None."""
    stderr_path = json_path.with_suffix(".stderr")
    if not stderr_path.exists():
        return None
    try:
        text = stderr_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    matches = _STDERR_TS_RE.findall(text)
    if len(matches) < 2:
        return None
    first = " ".join(matches[0][:2]) + ":" + matches[0][2] + ":" + matches[0][3]
    last = " ".join(matches[-1][:2]) + ":" + matches[-1][2] + ":" + matches[-1][3]
    return _seconds_between(first, last)


def _commit_hash(agg: dict[str, Any]) -> str | None:
    value = agg.get("commit_hash") or agg.get("commit")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _runtime_seconds(agg: dict[str, Any], json_path: Path) -> int | None:
    for key in ("runtime_seconds", "wallclock_s"):
        v = agg.get(key)
        if isinstance(v, int | float):
            return int(v)
    return _runtime_from_stderr(json_path)


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


def _make_run_id(dir_name: str, json_stem: str) -> str:
    """Construct a stable run_id from directory and json stem."""
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

    items: list[tuple[str, Path]] = []
    for item in sorted(RUNS_DIR.iterdir()):
        if item.is_dir():
            for jf in sorted(item.glob("*.json")):
                items.append((item.name, jf))

    for dir_label, jf in items:
        stem = jf.stem
        run_id = _make_run_id(dir_label, stem)

        if run_id in existing_ids:
            skipped.append(f"{run_id} (already recorded)")
            continue

        date_str = _parse_date_from_dir(dir_label)
        if date_str == "unknown":
            skipped.append(f"{run_id} (no parseable date in directory name)")
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
        loader_variant = _loader_variant_from_dir(dir_label)
        corpus = _infer_corpus_from_dir(dir_label)

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
            "source": f"eval/runs/{dir_label}/{jf.name}",
            "notes": "",
        }
        if loader_variant:
            run["loader_variant"] = loader_variant

        commit = _commit_hash(agg)
        if commit:
            run["commit_hash"] = commit

        runtime = _runtime_seconds(agg, jf)
        if runtime:
            run["runtime_seconds"] = runtime

        new_runs.append(run)
        added_ids.append(run_id)

    return new_runs, added_ids, skipped


def _sort_key(run: dict[str, Any]) -> tuple[str, str]:
    return (run.get("date", "0000-00-00"), run.get("run_id", ""))


_HTML_DATA_OPEN = '<script id="data" type="application/json">'
_HTML_DATA_CLOSE = "</script>"


def update_html_data_block(html_path: Path, json_text: str) -> None:
    """Replace the inline JSON data block in dashboard.html with *json_text*."""
    html = html_path.read_text(encoding="utf-8")

    open_idx = html.find(_HTML_DATA_OPEN)
    if open_idx == -1:
        raise ValueError(
            f"Marker '{_HTML_DATA_OPEN}' not found in {html_path}. "
            "Cannot update inline data block."
        )

    after_open = open_idx + len(_HTML_DATA_OPEN)
    close_idx = html.find(_HTML_DATA_CLOSE, after_open)
    if close_idx == -1:
        raise ValueError(
            f"Closing '{_HTML_DATA_CLOSE}' not found after data marker in {html_path}."
        )

    updated = html[:after_open] + "\n" + json_text + html[close_idx:]
    html_path.write_text(updated, encoding="utf-8")


def main() -> None:
    """Entry point: scan runs dir, merge with existing data, write output."""
    print(f"Loading existing data from {DASHBOARD_DATA}")
    data = _load_existing()
    pre_count = len(data.get("runs", []))
    data["runs"] = [
        r for r in data.get("runs", []) if r.get("date") not in (None, "", "unknown")
    ]
    pruned = pre_count - len(data["runs"])
    if pruned:
        print(f"  Pruned {pruned} existing run(s) with unknown date.")

    existing_ids = _existing_run_ids(data)
    print(f"  Retained {len(existing_ids)} existing run(s).")

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
