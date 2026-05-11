"""Build eval/dashboard_data.json and update the inline data block in eval/dashboard.html.

Idempotent: existing entries with the same run_id are preserved. New runs
found in eval/runs/ that are not already recorded are appended. Runs are
sorted in descending order by date (newest first), then by run_id.

Usage:
    uv run python scripts/build_eval_dashboard.py

The script strips all per-document records and filenames from the raw JSON
dumps before writing to dashboard_data.json. Only aggregate metrics are
committed to the summary file.

Runs whose directory name does not encode a parseable date are excluded
from the dashboard. Per-run runtime is computed from the first and last
timestamp in the run's `.stderr` file when present, with a fallback to
the stderr/json file mtimes when the stderr has no parseable timestamps
(e.g. eval ran with `--log quiet`). Commit hashes are read from the run
JSON when present; otherwise backfilled best-effort from the parent of
the commit that first added a tracked artifact in the run directory
(`~` suffix marks the value as derived rather than captured at run time).

Runs whose directory name starts with `baseline-` are tagged with
`baseline: true`. `scripts/build_eval_charts.py` reads this flag and
clips the static accuracy-over-time chart to runs at-or-after the most
recent baseline so the chart's leftmost point is always the current
reference run.

Dashboard inclusion policy (enforced at write time):
- Only synthetic-corpus runs are kept; real-world runs are dropped.
- Only runs with both `runtime_seconds` and `corpus_size` are kept, so
  the per-doc runtime cell renders for every row.

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
    "loader",
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

_STDERR_TS_RE = re.compile(r"(\d{4}-\d{2}-\d{2})[ T](\d{2}):(\d{2}):(\d{2})")
_RUN_ID_TS_RE = re.compile(r"(\d{8}-\d{6})")


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
    """Infer loader name from JSON filename convention (e.g. gemma4_docling.json).

    Historical runs may carry an `_unstructured` suffix; surface that as-is so
    older dashboard rows continue to render. Current runs are docling-only
    (ADR-006).
    """
    stem = Path(fname).stem
    parts = stem.split("_")
    if parts and parts[-1] in ("docling", "unstructured"):
        return parts[-1]
    return "unknown"


def _loader_from_comparisons(json_path: Path) -> str | None:
    """Read the first comparison's `loader_backend` for runs without a top-level
    `loader` field. Returns None if the file can't be read or has no signal.
    """
    if not json_path.exists():
        return None
    try:
        with json_path.open() as f:
            raw = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None
    comparisons = raw.get("comparisons")
    if not isinstance(comparisons, list) or not comparisons:
        return None
    backend = (
        comparisons[0].get("loader_backend")
        if isinstance(comparisons[0], dict)
        else None
    )
    return backend if isinstance(backend, str) and backend else None


def _resolve_loader(agg: dict[str, Any], json_path: Path) -> str:
    """Determine the loader for a run.

    Priority:
    1. Top-level `loader` field in the JSON (current `drover evaluate` output).
    2. First comparison's `loader_backend` (older drover JSON shape).
    3. Filename suffix convention (e.g. `gemma4_docling.json`).
    4. "unknown" if none of the above resolve.
    """
    top = agg.get("loader")
    if isinstance(top, str) and top.strip():
        return top.strip()
    from_comparisons = _loader_from_comparisons(json_path)
    if from_comparisons:
        return from_comparisons
    return _infer_loader_from_filename(json_path.name)


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


def _find_stderr_sibling(json_path: Path) -> Path | None:
    """Locate a `.stderr` file in the run directory (any stem)."""
    same_stem = json_path.with_suffix(".stderr")
    if same_stem.exists():
        return same_stem
    siblings = sorted(json_path.parent.glob("*.stderr"))
    return siblings[0] if siblings else None


def _runtime_from_mtimes(json_path: Path) -> int | None:
    """Fallback: estimate runtime from `.stderr` (start) and `.json` (end) mtimes.

    Used when `--log` was quiet so the stderr file has no parseable timestamps.
    The stderr file is created the moment the eval CLI's redirection opens, so
    its mtime closely tracks process start; the JSON file's mtime tracks the
    last write at process end. Falls back to any `.stderr` neighbour in the
    same directory if no same-stem match is found.
    """
    stderr_path = _find_stderr_sibling(json_path)
    if stderr_path is None or not json_path.exists():
        return None
    try:
        start = stderr_path.stat().st_mtime
        end = json_path.stat().st_mtime
    except OSError:
        return None
    delta = int(end - start)
    return delta if delta > 0 else None


def _commit_hash(agg: dict[str, Any]) -> str | None:
    value = agg.get("commit_hash") or agg.get("commit")
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def _git_artifact_introducing_commit(file_path: Path) -> str | None:
    """Return the short hash of the commit that first added *file_path*."""
    try:
        result = subprocess.run(  # nosec B603 B607 - fixed argv, trusted PATH
            [
                "git",
                "log",
                "--diff-filter=A",
                "-1",
                "--format=%h",
                "--",
                str(file_path),
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def _git_parent(short_hash: str) -> str | None:
    """Return the short hash of *short_hash*'s parent commit, or None."""
    try:
        result = subprocess.run(  # nosec B603 B607 - fixed argv, trusted PATH
            ["git", "rev-parse", "--short", f"{short_hash}^"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
    except (FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    sha = result.stdout.strip()
    return sha or None


def _commit_from_artifact_history(run_dir: Path) -> str | None:
    """Best-effort commit_hash for a run, derived from its committed artifacts.

    The eval workflow is "run eval -> commit artifacts", so the parent of the
    commit that first added a tracked file in the run directory is the commit
    that produced the eval. Returns a short hash with a `~` suffix to mark
    the value as derived (not captured at run time, may not reflect dirty-tree
    state).
    """
    for name in ("eval.stderr", "results.md"):
        candidate = run_dir / name
        if not candidate.exists():
            continue
        introducing = _git_artifact_introducing_commit(candidate)
        if not introducing:
            continue
        parent = _git_parent(introducing)
        if parent:
            return f"{parent}~"
    return None


def _runtime_seconds(agg: dict[str, Any], json_path: Path) -> int | None:
    for key in ("runtime_seconds", "wallclock_s"):
        v = agg.get(key)
        if isinstance(v, int | float):
            return int(v)
    runtime = _runtime_from_stderr(json_path)
    if runtime is not None:
        return runtime
    return _runtime_from_mtimes(json_path)


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

        loader = _resolve_loader(agg, jf)
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
        if dir_label.startswith("baseline-"):
            run["baseline"] = True

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
    """Sort runs chronologically.

    Prefer the YYYYMMDD-HHMMSS timestamp embedded in `run_id` (which the
    eval workflow encodes via `date +%Y%m%d-%H%M%S`) over the bare date,
    so multiple runs on the same day order by actual run time rather
    than alphabetic run_id prefix.
    """
    rid = run.get("run_id", "")
    match = _RUN_ID_TS_RE.search(rid)
    if match:
        return (match.group(1), rid)
    date = run.get("date", "0000-00-00")
    return (date.replace("-", "") + "-000000", rid)


def _qualifies_for_dashboard(run: dict[str, Any]) -> bool:
    """Dashboard inclusion policy.

    Runs are kept only if they are synthetic-corpus and have both a
    runtime_seconds and a corpus_size, so the per-doc runtime cell can be
    rendered. Real-world runs and runs predating runtime instrumentation
    are excluded.
    """
    if run.get("corpus") != "synthetic":
        return False
    runtime = run.get("runtime_seconds")
    size = run.get("corpus_size")
    if not isinstance(runtime, int | float) or runtime <= 0:
        return False
    return isinstance(size, int) and size > 0


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

    backfilled_runtime = 0
    backfilled_loader = 0
    backfilled_commit = 0
    for run in data["runs"]:
        source = run.get("source")
        json_path = REPO_ROOT / source if isinstance(source, str) else None
        json_available = json_path is not None and json_path.exists()
        run_dir = json_path.parent if json_path is not None else None

        if not isinstance(run.get("runtime_seconds"), int | float) and json_available:
            assert json_path is not None
            runtime = _runtime_seconds({}, json_path)
            if runtime:
                run["runtime_seconds"] = runtime
                backfilled_runtime += 1

        if run.get("loader", "unknown") in (None, "", "unknown") and json_available:
            assert json_path is not None
            better = _loader_from_comparisons(json_path)
            if better:
                run["loader"] = better
                backfilled_loader += 1

        existing_commit = run.get("commit_hash")
        commit_missing = not isinstance(existing_commit, str) or not existing_commit
        if commit_missing and run_dir is not None and run_dir.exists():
            derived = _commit_from_artifact_history(run_dir)
            if derived:
                run["commit_hash"] = derived
                backfilled_commit += 1
    if backfilled_runtime:
        print(f"  Backfilled runtime_seconds for {backfilled_runtime} existing run(s).")
    if backfilled_loader:
        print(f"  Backfilled loader for {backfilled_loader} existing run(s).")
    if backfilled_commit:
        print(
            f"  Backfilled commit_hash for {backfilled_commit} existing run(s) "
            "(derived; `~` suffix marks artifact-history origin)."
        )

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

    pre_filter = len(data["runs"])
    dropped = [r for r in data["runs"] if not _qualifies_for_dashboard(r)]
    data["runs"] = [r for r in data["runs"] if _qualifies_for_dashboard(r)]
    if dropped:
        print(
            f"\nDropped {len(dropped)} run(s) failing dashboard policy "
            f"(must be synthetic with runtime_seconds and corpus_size):"
        )
        for r in dropped:
            reason = []
            if r.get("corpus") != "synthetic":
                reason.append(f"corpus={r.get('corpus')}")
            if not isinstance(r.get("runtime_seconds"), int | float):
                reason.append("no runtime_seconds")
            if not isinstance(r.get("corpus_size"), int):
                reason.append("no corpus_size")
            print(f"  - {r.get('run_id')} ({', '.join(reason) or 'unknown reason'})")
    print(f"\n{pre_filter} -> {len(data['runs'])} run(s) after policy filter.")

    data["runs"].sort(key=_sort_key, reverse=True)
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
