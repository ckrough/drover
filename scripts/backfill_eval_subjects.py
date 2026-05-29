#!/usr/bin/env python3
"""Backfill content-based subjects into the synthetic eval ground truth.

prof-cgu: rows in eval/ground_truth/synthetic.jsonl historically carried the
document-type subject form (e.g. ``estate will``) that the file's own header
prohibits. This one-shot tool reads each document's PDF, asks the model for a
2-4 word content subject via ``generate_eval_samples._subject_from_text``, and
rewrites that row's ``subject`` in place.

Each row already carries a ``subject`` key, so the value is rewritten in
place; comment lines and every other field (e.g. ``entity``) are preserved
unchanged. The PDFs, filenames, dates, and vendors are untouched.

Usage:
    uv run --with pypdf python scripts/backfill_eval_subjects.py --dry-run
    uv run --with pypdf python scripts/backfill_eval_subjects.py --max-cost-usd 3
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

if TYPE_CHECKING:
    from collections import Counter

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from generate_eval_samples import (
    MODEL_PRICING,
    EmptyDocumentTextError,
    _anthropic_client,
    _estimate_cost,
    _subject_from_text,
    _write_text_atomic,
)


def _extract_text(pdf_path: Path) -> str:
    """Return the concatenated text layer of a PDF (no OCR).

    The eval PDFs are reportlab-rendered from markdown and carry a clean text
    layer, so a plain text-layer read is faster and lighter than Docling's
    full-page-OCR loader and is sufficient to derive a short content subject.
    """
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _data_rows(lines: list[str]) -> list[tuple[int, dict[str, Any]]]:
    """Return (line_index, parsed_dict) for each JSONL data row."""
    rows: list[tuple[int, dict[str, Any]]] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        try:
            obj = json.loads(stripped)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and "filename" in obj:
            rows.append((i, obj))
    return rows


def _forbidden_form(obj: dict[str, Any]) -> str:
    """The ``f'{category} {doctype}'`` form prof-cgu set out to eliminate."""
    cat = str(obj.get("category", "")).replace("_", " ")
    dt = str(obj.get("doctype", "")).replace("_", " ")
    return f"{cat} {dt}".strip()


async def _drain(tasks: list[asyncio.Task[Any]]) -> None:
    """Cancel and await any tasks still pending, swallowing CancelledError.

    The in-flight HTTP calls Anthropic has already received will still bill
    (asyncio cannot un-send a request), but the loop exits without
    'Task was destroyed but it is pending' warnings or unclean socket
    teardown.
    """
    for t in tasks:
        if not t.done():
            t.cancel()
    for t in tasks:
        with contextlib.suppress(BaseException):
            await t


async def _backfill(
    *,
    ground_truth: Path,
    lines: list[str],
    rows: list[tuple[int, dict[str, Any]]],
    documents_dir: Path,
    model: str,
    concurrency: int,
    max_cost_usd: float,
) -> int:
    client = _anthropic_client(model, max_retries=3, timeout_seconds=120)
    sem = asyncio.Semaphore(concurrency)

    async def _one(idx: int, obj: dict[str, Any]) -> tuple[int, str, Counter[str]]:
        async with sem:
            pdf = documents_dir / obj["filename"]
            text = await asyncio.to_thread(_extract_text, pdf)
            subject, usage = await _subject_from_text(
                client, text, forbidden=_forbidden_form(obj)
            )
            return idx, subject, usage

    tasks: list[asyncio.Task[Any]] = [
        asyncio.create_task(_one(i, obj)) for i, obj in rows
    ]

    click.echo("# Subject backfill")
    click.echo(f"# rows={len(rows)} model={model}")
    click.echo("| filename | old subject | new subject | cost_usd |")
    click.echo("|----------|-------------|-------------|----------|")

    # Collect first, apply at the end — separating the two means an abort
    # cannot leave `lines` half-rewritten and a future refactor cannot ship
    # a partial-write regression.
    results: dict[int, str] = {}
    cost = 0.0
    aborted = False
    by_index = dict(rows)

    for coro in asyncio.as_completed(tasks):
        try:
            idx, subject, usage = await coro
        except EmptyDocumentTextError as exc:
            click.echo(f"ERROR: {exc}", err=True)
            await _drain(tasks)
            return 2
        except Exception as exc:
            click.echo(f"ERROR: per-row task failed: {exc!r}", err=True)
            await _drain(tasks)
            return 3
        results[idx] = subject
        call_cost = _estimate_cost(usage, model)
        cost += call_cost
        obj = by_index[idx]
        old = obj.get("subject", "")
        click.echo(f"| {obj['filename']} | {old} | {subject} | {call_cost:.5f} |")
        if cost > max_cost_usd:
            click.echo(
                f"\nABORT: cumulative cost ${cost:.2f} exceeds "
                f"--max-cost-usd ${max_cost_usd:.2f}; no file written.",
                err=True,
            )
            aborted = True
            break

    await _drain(tasks)
    if aborted:
        return 1

    for idx, subject in results.items():
        obj = by_index[idx]
        obj["subject"] = subject  # reassignment preserves key position
        newline = "\n" if lines[idx].endswith("\n") else ""
        lines[idx] = json.dumps(obj) + newline
    _write_text_atomic(ground_truth, "".join(lines))

    click.echo(f"\nsummary: rewritten={len(results)} cost_usd={cost:.4f}")
    return 0


@click.command()
@click.option("--ai-model", default="claude-sonnet-4-6", show_default=True)
@click.option("--concurrency", type=int, default=5, show_default=True)
@click.option("--max-cost-usd", type=float, default=6.00, show_default=True)
@click.option(
    "--ground-truth",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("eval/ground_truth/synthetic.jsonl"),
    show_default=True,
)
@click.option(
    "--documents-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("eval/samples/synthetic"),
    show_default=True,
)
@click.option("--dry-run", is_flag=True, default=False)
def main(
    ai_model: str,
    concurrency: int,
    max_cost_usd: float,
    ground_truth: Path,
    documents_dir: Path,
    dry_run: bool,
) -> None:
    """Rewrite the `subject` of every synthetic eval row from its content."""
    if not dry_run and ai_model not in MODEL_PRICING:
        click.echo(
            f"ERROR: --ai-model {ai_model!r} has no pricing entry in "
            f"MODEL_PRICING ({sorted(MODEL_PRICING)}); cost cap would be "
            "silently disabled. Add pricing or pick a priced model.",
            err=True,
        )
        raise SystemExit(2)

    lines = ground_truth.read_text(encoding="utf-8").splitlines(keepends=True)
    rows = _data_rows(lines)
    missing = [
        obj["filename"]
        for _, obj in rows
        if not (documents_dir / obj["filename"]).exists()
    ]
    if missing:
        click.echo(f"ERROR: {len(missing)} PDFs missing: {missing[:5]}", err=True)
        raise SystemExit(2)

    if dry_run:
        click.echo(f"# dry-run: {len(rows)} rows; no API calls or writes.")
        click.echo("| filename | current subject |")
        click.echo("|----------|-----------------|")
        for _, obj in rows:
            click.echo(f"| {obj['filename']} | {obj.get('subject', '')} |")
        return

    exit_code = asyncio.run(
        _backfill(
            ground_truth=ground_truth,
            lines=lines,
            rows=rows,
            documents_dir=documents_dir,
            model=ai_model,
            concurrency=concurrency,
            max_cost_usd=max_cost_usd,
        )
    )
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
