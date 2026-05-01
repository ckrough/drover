"""Run drover evaluate for one (loader, provider) combo and emit a one-line summary.

Used by `eval/baselines.md` to capture per-axis accuracies for the
prof-nft Docling-vs-unstructured comparison. The orchestration is a
shell loop so we don't grow a heavy harness:

    for LOADER in unstructured docling; do
      uv run python scripts/benchmark_docling_loaders.py \\
        --loader $LOADER --ai-provider ollama --ai-model gemma4:latest
    done

Each invocation runs `drover evaluate ... --output json`, captures the
total wallclock, parses the JSON, and prints a single line that the
human curator can paste into the markdown table.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import cast


def _strip_to_json(stdout: str) -> dict[str, object]:
    """Pull the first balanced top-level JSON object out of mixed stdout."""
    match = re.search(r"\{.*\}", stdout, flags=re.DOTALL)
    if not match:
        raise RuntimeError(f"No JSON object found in evaluate output:\n{stdout[:400]}")
    return json.loads(match.group(0))


def _avg_loader_latency(comparisons: list[dict[str, object]]) -> float | None:
    """Return mean loader_latency_ms across comparisons, or None if absent."""
    samples = [
        float(c["loader_latency_ms"])
        for c in comparisons
        if isinstance(c.get("loader_latency_ms"), int | float)
    ]
    return sum(samples) / len(samples) if samples else None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--loader", required=True, choices=["unstructured", "docling"])
    parser.add_argument("--ai-provider", required=True)
    parser.add_argument("--ai-model", default="")
    parser.add_argument(
        "--ground-truth", default="eval/ground_truth/synthetic.jsonl", type=Path
    )
    parser.add_argument("--documents-dir", default="eval/samples/synthetic", type=Path)
    parser.add_argument(
        "--out-json",
        type=Path,
        default=None,
        help="Optional path to write the full evaluate JSON for archival.",
    )
    args = parser.parse_args()

    cmd = [
        "uv",
        "run",
        "drover",
        "evaluate",
        "--ground-truth",
        str(args.ground_truth),
        "--documents-dir",
        str(args.documents_dir),
        "--ai-provider",
        args.ai_provider,
        "--loader",
        args.loader,
        "--output",
        "json",
        "--log",
        "quiet",
    ]
    if args.ai_model:
        cmd.extend(["--ai-model", args.ai_model])

    start = time.perf_counter()
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    elapsed_s = time.perf_counter() - start

    if proc.returncode not in (0, 1):
        sys.stderr.write(proc.stdout)
        sys.stderr.write(proc.stderr)
        return proc.returncode

    payload = _strip_to_json(proc.stdout)

    if args.out_json is not None:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(payload, indent=2))

    comparisons = cast(list[dict[str, object]], payload.get("comparisons") or [])
    avg_lat = _avg_loader_latency(comparisons)

    label = f"{args.ai_provider}/{args.ai_model or 'default'} + {args.loader}"
    line = (
        f"{label}: total={payload.get('total')} "
        f"domain={payload.get('domain_accuracy'):.3f} "
        f"category={payload.get('category_accuracy'):.3f} "
        f"doctype={payload.get('doctype_accuracy'):.3f} "
    )
    if payload.get("vendor_accuracy") is not None:
        vendor_acc = cast(float, payload["vendor_accuracy"])
        line += f"vendor={vendor_acc:.3f} "
    if payload.get("date_accuracy") is not None:
        date_acc = cast(float, payload["date_accuracy"])
        line += f"date={date_acc:.3f} "
    line += f"wallclock_s={elapsed_s:.1f}"
    if avg_lat is not None:
        line += f" avg_loader_ms={avg_lat:.1f}"

    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
