#!/usr/bin/env python3
"""Harvester: collect classification tuples from a real-world corpus.

Runs Drover in fallback mode locally (Ollama recommended) over a directory
of documents and emits a single PII-safe JSON aggregate suitable for
taxonomy-improvement analysis. The artifact contains only counts and
aggregated terms - no filenames, no document text, no per-document records
linking vendor to date to tuple.

Reuses helpers from scripts/discover_taxonomy_terms.py.

Usage:
    uv run python scripts/collect_classification_tuples.py \
        ~/Documents/personal-archive \
        --output eval/runs/$(date +%Y%m%d-%H%M%S)/realworld-tuples.json

    uv run python scripts/collect_classification_tuples.py \
        ~/Documents/personal-archive \
        --sample 200 --seed 42 \
        --output realworld-tuples.json
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))

from discover_taxonomy_terms import expand_paths, parse_llm_response

from drover.config import (
    AIConfig,
    AIProvider,
    DroverConfig,
    SampleStrategy,
    TaxonomyMode,
)
from drover.service import ClassificationService
from drover.taxonomy.loader import get_taxonomy

if TYPE_CHECKING:
    from drover.taxonomy.base import BaseTaxonomy


def _norm(value: str | None) -> str | None:
    """Normalize an LLM string output: lowercase, trim, underscores."""
    if value is None:
        return None
    cleaned = str(value).lower().strip().replace(" ", "_")
    return cleaned or None


def _norm_vendor(value: str | None) -> str | None:
    """Normalize a vendor name for aggregation: lowercase, hyphenated."""
    if value is None:
        return None
    cleaned = str(value).strip().lower()
    cleaned = re.sub(r"\s+", "-", cleaned)
    cleaned = re.sub(r"[^a-z0-9\-]+", "", cleaned)
    return cleaned or None


def _year_bucket(value: str | None) -> str | None:
    """Bucket a date string by year. Returns None if no year is parseable."""
    if value is None:
        return None
    match = re.search(r"(19|20)\d{2}", str(value))
    return match.group(0) if match else None


class TupleCollector:
    """Accumulates raw + canonical tuples and frequencies for the harvester."""

    def __init__(self, taxonomy: BaseTaxonomy) -> None:
        self.taxonomy = taxonomy
        self.processed = 0
        self.errors = 0

        # Term frequencies (raw and canonical)
        self.raw_domains: dict[str, int] = defaultdict(int)
        self.raw_categories: dict[str, int] = defaultdict(int)
        self.raw_doctypes: dict[str, int] = defaultdict(int)
        self.canonical_domains: dict[str, int] = defaultdict(int)
        self.canonical_categories: dict[str, int] = defaultdict(int)
        self.canonical_doctypes: dict[str, int] = defaultdict(int)

        # Drift records: (field, raw, canonical, domain) -> count
        # domain is "" for domain/doctype fields.
        self.drift: dict[tuple[str, str, str | None, str], int] = defaultdict(int)

        # Tuples (counts only)
        self.raw_tuples: dict[tuple[str, str, str], int] = defaultdict(int)
        self.canonical_tuples: dict[tuple[str | None, str | None, str | None], int] = (
            defaultdict(int)
        )

        # Vendor and date aggregates (independent, not joined to tuples).
        self.vendors: dict[str, int] = defaultdict(int)
        self.dates: dict[str, int] = defaultdict(int)

    def add(self, raw: dict[str, Any]) -> None:
        """Record one parsed LLM response."""
        raw_domain = _norm(raw.get("domain"))
        raw_category = _norm(raw.get("category"))
        raw_doctype = _norm(raw.get("doctype"))

        if not (raw_domain and raw_category and raw_doctype):
            self.errors += 1
            return

        canon_domain = self.taxonomy.canonical_domain(raw_domain)
        canon_category = (
            self.taxonomy.canonical_category(canon_domain, raw_category)
            if canon_domain
            else None
        )
        canon_doctype = self.taxonomy.canonical_doctype(raw_doctype)

        # Frequencies
        self.raw_domains[raw_domain] += 1
        self.raw_categories[raw_category] += 1
        self.raw_doctypes[raw_doctype] += 1
        if canon_domain:
            self.canonical_domains[canon_domain] += 1
        if canon_category:
            self.canonical_categories[canon_category] += 1
        if canon_doctype:
            self.canonical_doctypes[canon_doctype] += 1

        # Drift: only record where raw != canonical (or canonical is None).
        if raw_domain != canon_domain:
            self.drift[("domain", raw_domain, canon_domain, "")] += 1
        category_domain_key = canon_domain or raw_domain
        if raw_category != canon_category:
            self.drift[
                ("category", raw_category, canon_category, category_domain_key)
            ] += 1
        if raw_doctype != canon_doctype:
            self.drift[("doctype", raw_doctype, canon_doctype, "")] += 1

        # Tuples
        self.raw_tuples[(raw_domain, raw_category, raw_doctype)] += 1
        self.canonical_tuples[(canon_domain, canon_category, canon_doctype)] += 1

        # Vendor / date aggregates (no per-record join)
        vendor = _norm_vendor(raw.get("vendor"))
        if vendor:
            self.vendors[vendor] += 1
        year = _year_bucket(raw.get("date"))
        if year:
            self.dates[year] += 1

        self.processed += 1

    def to_json_dict(
        self, *, model: str, taxonomy_name: str, corpus_size: int
    ) -> dict[str, Any]:
        """Render the collected aggregates as a JSON-ready dict."""
        return {
            "metadata": {
                "corpus_size": corpus_size,
                "processed": self.processed,
                "errors": self.errors,
                "model": model,
                "taxonomy": taxonomy_name,
                "timestamp": datetime.now(UTC).isoformat(),
            },
            "raw_term_frequency": {
                "domains": _sorted_freq(self.raw_domains),
                "categories": _sorted_freq(self.raw_categories),
                "doctypes": _sorted_freq(self.raw_doctypes),
            },
            "canonical_term_frequency": {
                "domains": _sorted_freq(self.canonical_domains),
                "categories": _sorted_freq(self.canonical_categories),
                "doctypes": _sorted_freq(self.canonical_doctypes),
            },
            "drift": [
                {
                    "field": field,
                    "raw": raw,
                    "canonical": canon,
                    "domain": domain or None,
                    "count": count,
                }
                for (field, raw, canon, domain), count in sorted(
                    self.drift.items(), key=lambda kv: -kv[1]
                )
            ],
            "raw_tuples": [
                {"domain": d, "category": c, "doctype": t, "count": n}
                for (d, c, t), n in sorted(
                    self.raw_tuples.items(), key=lambda kv: -kv[1]
                )
            ],
            "canonical_tuples": [
                {"domain": d, "category": c, "doctype": t, "count": n}
                for (d, c, t), n in sorted(
                    self.canonical_tuples.items(), key=lambda kv: -kv[1]
                )
            ],
            "vendor_frequency": _sorted_freq(self.vendors),
            "date_frequency": _sorted_freq(self.dates),
        }


def _sorted_freq(counter: dict[str, int]) -> dict[str, int]:
    """Return a dict sorted by descending count, then key."""
    return dict(sorted(counter.items(), key=lambda kv: (-kv[1], kv[0])))


async def harvest(
    files: list[Path],
    config: DroverConfig,
    collector: TupleCollector,
    *,
    verbose: bool,
) -> None:
    """Classify each file and feed parsed responses to the collector."""
    service = ClassificationService(config)
    total = len(files)

    for idx, file_path in enumerate(files, 1):
        if verbose:
            click.echo(f"[{idx}/{total}]", err=True)

        try:
            loaded = await service._loader.load(file_path)
            _classification, debug_info = await service._classifier.classify(
                content=loaded.content,
                capture_debug=True,
                collect_metrics=False,
            )
            response = (debug_info or {}).get("response")
            raw = parse_llm_response(response) if response else None
            if raw is None:
                collector.errors += 1
                continue
            collector.add(raw)
        except Exception as e:
            collector.errors += 1
            if verbose:
                click.echo(f"    error: {type(e).__name__}", err=True)


@click.command()
@click.argument(
    "paths", nargs=-1, type=click.Path(exists=True, path_type=Path), required=True
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    required=True,
    help="Output JSON file (will be overwritten).",
)
@click.option(
    "--taxonomy",
    "taxonomy_name",
    type=str,
    default="household",
    show_default=True,
    help="Taxonomy to canonicalize against.",
)
@click.option(
    "--ai-provider",
    type=click.Choice([p.value for p in AIProvider], case_sensitive=False),
    default=None,
    help="AI provider (default: from config/env).",
)
@click.option(
    "--ai-model",
    type=str,
    default=None,
    help="AI model (default: from config/env).",
)
@click.option(
    "--sample",
    "-s",
    type=int,
    default=None,
    help="Randomly sample up to N files from the corpus.",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducible sampling.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Print progress to stderr.",
)
def main(
    paths: tuple[Path, ...],
    output: Path,
    taxonomy_name: str,
    ai_provider: str | None,
    ai_model: str | None,
    sample: int | None,
    seed: int | None,
    verbose: bool,
) -> None:
    """Harvest classification tuples for taxonomy-improvement analysis.

    Walks PATHS (files or directories), classifies each document in fallback
    mode, and writes a single PII-safe JSON aggregate to --output.
    """
    files = expand_paths(list(paths))
    if not files:
        click.echo("No supported document files found.", err=True)
        sys.exit(1)

    total_found = len(files)
    if sample is not None and 0 < sample < len(files):
        if seed is not None:
            random.seed(seed)
        files = random.sample(files, sample)
        click.echo(f"Found {total_found} documents, sampling {len(files)}.", err=True)
    else:
        click.echo(f"Found {len(files)} documents.", err=True)

    taxonomy = get_taxonomy(taxonomy_name)

    ai_kwargs: dict[str, Any] = {}
    if ai_provider:
        ai_kwargs["provider"] = AIProvider(ai_provider)
    if ai_model:
        ai_kwargs["model"] = ai_model

    config = DroverConfig(
        ai=AIConfig(**ai_kwargs) if ai_kwargs else AIConfig(),
        taxonomy=taxonomy_name,
        taxonomy_mode=TaxonomyMode.FALLBACK,
        sample_strategy=SampleStrategy.ADAPTIVE,
        capture_debug=True,
    )

    click.echo(f"Provider: {config.ai.provider.value}", err=True)
    click.echo(f"Model:    {config.ai.model}", err=True)
    click.echo(f"Taxonomy: {taxonomy_name}", err=True)
    click.echo("", err=True)

    collector = TupleCollector(taxonomy)
    asyncio.run(harvest(files, config, collector, verbose=verbose))

    payload = collector.to_json_dict(
        model=f"{config.ai.provider.value}/{config.ai.model}",
        taxonomy_name=taxonomy_name,
        corpus_size=len(files),
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, sort_keys=False))
    click.echo("", err=True)
    click.echo(
        f"Wrote {output} (processed={collector.processed}, errors={collector.errors})",
        err=True,
    )


if __name__ == "__main__":
    main()
