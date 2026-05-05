#!/usr/bin/env python3
"""Taxonomy discovery script for collecting LLM-suggested classification terms.

Runs Drover in fallback mode on documents and captures the raw LLM suggestions
(before normalization) to discover new domains, categories, and document types
for taxonomy improvement.

Usage:
    python scripts/discover_taxonomy_terms.py documents/*.pdf
    python scripts/discover_taxonomy_terms.py --format json ~/Documents
    python scripts/discover_taxonomy_terms.py --output discovered.py documents/
    python scripts/discover_taxonomy_terms.py --sample 50 ~/Documents
    python scripts/discover_taxonomy_terms.py --sample 100 --seed 42 ~/Documents
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import random
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import click

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from drover.config import (
    AIConfig,
    AIProvider,
    DroverConfig,
    SampleStrategy,
    TaxonomyMode,
)
from drover.service import ClassificationService


class TaxonomyCollector:
    """Collects and organizes discovered taxonomy terms."""

    def __init__(self) -> None:
        self.domains: set[str] = set()
        self.categories: dict[str, set[str]] = defaultdict(set)
        self.doctypes: set[str] = set()
        self.file_count: int = 0
        self.error_count: int = 0

    def add(self, domain: str, category: str, doctype: str) -> None:
        """Add a classification result to the collection."""
        # Normalize values (lowercase, underscores)
        domain = self._normalize(domain)
        category = self._normalize(category)
        doctype = self._normalize(doctype)

        self.domains.add(domain)
        self.categories[domain].add(category)
        self.doctypes.add(doctype)
        self.file_count += 1

    def _normalize(self, value: str) -> str:
        """Normalize a taxonomy value."""
        return value.lower().strip().replace(" ", "_").replace("-", "_")

    def to_python(self) -> str:
        """Format the collected taxonomy as Python code."""
        lines = [
            '"""Discovered taxonomy terms from document classification.',
            "",
            "These terms were suggested by the LLM during classification.",
            "Review and merge into the main taxonomy as appropriate.",
            '"""',
            "",
            "from typing import ClassVar",
            "",
            "",
            f"# Discovered from {self.file_count} documents ({self.error_count} errors)",
            "",
            "DISCOVERED_DOMAINS: ClassVar[set[str]] = {",
        ]

        # Domains
        for domain in sorted(self.domains):
            lines.append(f'    "{domain}",')
        lines.append("}")
        lines.append("")

        # Categories
        lines.append("DISCOVERED_CATEGORIES: ClassVar[dict[str, set[str]]] = {")
        for domain in sorted(self.categories.keys()):
            lines.append(f'    "{domain}": {{')
            for category in sorted(self.categories[domain]):
                lines.append(f'        "{category}",')
            lines.append("    },")
        lines.append("}")
        lines.append("")

        # Doctypes
        lines.append("DISCOVERED_DOCTYPES: ClassVar[set[str]] = {")
        for doctype in sorted(self.doctypes):
            lines.append(f'    "{doctype}",')
        lines.append("}")
        lines.append("")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Format the collected taxonomy as JSON."""
        data = {
            "metadata": {
                "file_count": self.file_count,
                "error_count": self.error_count,
            },
            "domains": sorted(self.domains),
            "categories": {
                domain: sorted(cats) for domain, cats in sorted(self.categories.items())
            },
            "doctypes": sorted(self.doctypes),
        }
        return json.dumps(data, indent=2)


def parse_llm_response(response: str) -> dict[str, Any] | None:
    """Parse raw LLM response to extract classification fields.

    This mirrors the logic in classifier._parse_response() but doesn't
    raise exceptions - returns None on parse failure.
    """
    response = response.strip()

    # Handle chain-of-thought format with <classification_analysis> tags
    close_tag = "</classification_analysis>"
    if close_tag in response:
        response = response.split(close_tag, 1)[1].strip()

    parsed = None

    # Try direct JSON parse
    with contextlib.suppress(json.JSONDecodeError):
        parsed = json.loads(response)

    # Handle template-style double-brace wrappers like `{{ ... }}`
    if parsed is None and response.startswith("{{") and response.endswith("}}"):
        candidate = "{" + response[2:-2].strip() + "}"
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            response = candidate

    # Try extracting from markdown code blocks
    if parsed is None:
        code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if code_match:
            block = code_match.group(1).strip()
            with contextlib.suppress(json.JSONDecodeError):
                parsed = json.loads(block)

    # Try extracting largest JSON object
    if parsed is None:
        candidate = _extract_largest_json_object(response)
        if candidate is not None:
            with contextlib.suppress(json.JSONDecodeError):
                parsed = json.loads(candidate)

    if parsed is None:
        return None

    # Validate required fields
    required_fields = {"domain", "category", "doctype"}
    if not all(field in parsed for field in required_fields):
        return None

    return parsed


def _extract_largest_json_object(text: str) -> str | None:
    """Extract the largest balanced JSON object substring from text."""
    best_span: tuple[int, int] | None = None
    depth = 0
    start_idx: int | None = None
    in_string = False
    escape = False

    for idx, ch in enumerate(text):
        if ch == '"' and not escape:
            in_string = not in_string
        escape = ch == "\\" and not escape

        if in_string:
            continue

        if ch == "{":
            if depth == 0:
                start_idx = idx
            depth += 1
        elif ch == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start_idx is not None:
                    end_idx = idx + 1
                    if best_span is None or (end_idx - start_idx) > (
                        best_span[1] - best_span[0]
                    ):
                        best_span = (start_idx, end_idx)

    if best_span is None:
        return None

    return text[best_span[0] : best_span[1]]


def expand_paths(paths: list[Path]) -> list[Path]:
    """Expand directories to document files and filter to supported types."""
    supported_extensions = {
        ".pdf",
        ".doc",
        ".docx",
        ".xls",
        ".xlsx",
        ".ppt",
        ".pptx",
        ".txt",
        ".md",
        ".rtf",
        ".odt",
        ".ods",
        ".odp",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".tiff",
        ".bmp",
        ".webp",
    }

    result = []
    for path in paths:
        path = path.expanduser()
        if path.is_dir():
            for child in path.rglob("*"):
                if child.is_file() and child.suffix.lower() in supported_extensions:
                    result.append(child)
        elif path.is_file():
            if path.suffix.lower() in supported_extensions:
                result.append(path)
            else:
                click.echo(f"Skipping unsupported file: {path}", err=True)
    return sorted(set(result))


async def run_discovery(
    files: list[Path],
    config: DroverConfig,
    collector: TaxonomyCollector,
    verbose: bool = False,
) -> None:
    """Run classification on files and collect raw taxonomy terms."""
    service = ClassificationService(config)
    total = len(files)

    for idx, file_path in enumerate(files, 1):
        if verbose:
            click.echo(f"[{idx}/{total}] {file_path.name}", err=True)

        try:
            # Call classify_file but we need the debug_info
            # We'll modify our approach - use the classifier directly
            loaded = await service._loader.load(file_path)

            _classification, debug_info = await service._classifier.classify(
                content=loaded.content,
                capture_debug=True,
                collect_metrics=False,
            )

            # Parse the raw response (before normalization)
            if debug_info and "response" in debug_info:
                raw = parse_llm_response(debug_info["response"])
                if raw:
                    collector.add(raw["domain"], raw["category"], raw["doctype"])
                    if verbose:
                        click.echo(
                            f"    -> {raw['domain']}/{raw['category']}/{raw['doctype']}",
                            err=True,
                        )
                else:
                    collector.error_count += 1
                    if verbose:
                        click.echo("    -> Failed to parse response", err=True)
            else:
                collector.error_count += 1
                if verbose:
                    click.echo("    -> No debug info captured", err=True)

        except Exception as e:
            collector.error_count += 1
            if verbose:
                click.echo(f"    -> Error: {e}", err=True)


@click.command()
@click.argument(
    "paths", nargs=-1, type=click.Path(exists=True, path_type=Path), required=True
)
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["python", "json"], case_sensitive=False),
    default="python",
    help="Output format (default: python)",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output file (default: stdout)",
)
@click.option(
    "--ai-provider",
    type=click.Choice([p.value for p in AIProvider], case_sensitive=False),
    default=None,
    help="AI provider (default: from config/env)",
)
@click.option(
    "--ai-model",
    type=str,
    default=None,
    help="AI model (default: from config/env)",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Show progress for each file",
)
@click.option(
    "--sample",
    "-s",
    type=int,
    default=None,
    help="Randomly sample up to N files from the results",
)
@click.option(
    "--seed",
    type=int,
    default=None,
    help="Random seed for reproducible sampling",
)
def main(
    paths: tuple[Path, ...],
    output_format: str,
    output: Path | None,
    ai_provider: str | None,
    ai_model: str | None,
    verbose: bool,
    sample: int | None,
    seed: int | None,
) -> None:
    """Discover taxonomy terms from document classifications.

    Runs Drover classification on the specified files/directories and
    captures the raw LLM suggestions (before normalization) to identify
    new domains, categories, and document types.

    \b
    Examples:
        python scripts/discover_taxonomy_terms.py documents/*.pdf
        python scripts/discover_taxonomy_terms.py --format json ~/Documents
        python scripts/discover_taxonomy_terms.py -v --output discovered.py documents/
        python scripts/discover_taxonomy_terms.py --sample 50 ~/Documents
        python scripts/discover_taxonomy_terms.py --sample 100 --seed 42 ~/Documents
    """
    # Expand paths and collect files
    files = expand_paths(list(paths))
    if not files:
        click.echo("No supported document files found.", err=True)
        sys.exit(1)

    total_found = len(files)

    # Apply random sampling if requested
    if sample is not None and sample > 0 and sample < len(files):
        if seed is not None:
            random.seed(seed)  # nosec B311 - non-cryptographic sampling
        files = random.sample(files, sample)  # nosec B311 - non-cryptographic sampling
        click.echo(f"Found {total_found} documents, sampling {len(files)}", err=True)
    else:
        click.echo(f"Found {len(files)} documents to classify", err=True)

    # Build config
    ai_config_kwargs: dict[str, Any] = {}
    if ai_provider:
        ai_config_kwargs["provider"] = AIProvider(ai_provider)
    if ai_model:
        ai_config_kwargs["model"] = ai_model

    config = DroverConfig(
        ai=AIConfig(**ai_config_kwargs) if ai_config_kwargs else AIConfig(),
        taxonomy_mode=TaxonomyMode.FALLBACK,
        sample_strategy=SampleStrategy.ADAPTIVE,
        capture_debug=True,
    )

    click.echo(f"Using provider: {config.ai.provider.value}", err=True)
    click.echo(f"Using model: {config.ai.model}", err=True)
    click.echo("", err=True)

    # Run discovery
    collector = TaxonomyCollector()
    asyncio.run(run_discovery(files, config, collector, verbose))

    # Generate output
    result = collector.to_python() if output_format == "python" else collector.to_json()

    if output:
        output.write_text(result)
        click.echo(f"Output written to: {output}", err=True)
    else:
        click.echo(result)

    # Summary
    click.echo("", err=True)
    click.echo(
        f"Discovered: {len(collector.domains)} domains, "
        f"{sum(len(c) for c in collector.categories.values())} categories, "
        f"{len(collector.doctypes)} doctypes",
        err=True,
    )
    if collector.error_count:
        click.echo(f"Errors: {collector.error_count}", err=True)


if __name__ == "__main__":
    main()
