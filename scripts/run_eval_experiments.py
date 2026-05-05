#!/usr/bin/env python3
"""Evaluation runner for testing drover classification against ground truth.

This script runs classification experiments across multiple models and documents,
recording results for analysis.

Usage:
    python scripts/run_eval_experiments.py run eval/experiment.yaml
    python scripts/run_eval_experiments.py report eval/results/experiment-*.jsonl
    python scripts/run_eval_experiments.py validate eval/experiment.yaml

Dashboard hint:
    After producing eval runs that you want surfaced in the dashboard, run
    `uv run python scripts/build_eval_dashboard.py` to refresh
    `eval/dashboard.html` and `eval/dashboard_data.json`.
"""

from __future__ import annotations

import asyncio
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import click
import yaml
from pydantic import BaseModel, Field, ValidationError, field_validator

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from drover.config import (
    AIConfig,
    AIProvider,
    DroverConfig,
    SampleStrategy,
    TaxonomyMode,
)
from drover.models import ClassificationErrorResult, ClassificationResult
from drover.service import ClassificationService

# -----------------------------------------------------------------------------
# Manifest Schema (Pydantic Models)
# -----------------------------------------------------------------------------


class ModelConfig(BaseModel):
    """Configuration for a single model to test."""

    provider: AIProvider
    model: str


class ExpectedClassification(BaseModel):
    """Ground truth classification for a document."""

    domain: str
    category: str
    doctype: str
    vendor: str
    date: str
    subject: str


class DocumentEntry(BaseModel):
    """A document with its expected classification."""

    path: Path
    expected: ExpectedClassification

    @field_validator("path", mode="before")
    @classmethod
    def expand_path(cls, v: str | Path) -> Path:
        """Convert string to Path and expand user."""
        return Path(v).expanduser()


class SharedConfig(BaseModel):
    """Shared configuration applied to all runs."""

    taxonomy: str = "household"
    taxonomy_mode: TaxonomyMode = TaxonomyMode.FALLBACK
    sample_strategy: SampleStrategy = SampleStrategy.ADAPTIVE
    max_pages: int = 10
    max_tokens: int = 4000
    prompt: Path | None = None
    capture_debug: bool = False
    debug_dir: Path | None = None

    @field_validator("prompt", mode="before")
    @classmethod
    def expand_prompt_path(cls, v: str | Path | None) -> Path | None:
        """Convert string to Path and expand user."""
        if v is None:
            return None
        return Path(v).expanduser()

    @field_validator("debug_dir", mode="before")
    @classmethod
    def expand_debug_dir_path(cls, v: str | Path | None) -> Path | None:
        """Convert string to Path and expand user."""
        if v is None:
            return None
        return Path(v).expanduser()


class ExperimentManifest(BaseModel):
    """Complete experiment manifest."""

    name: str
    description: str = ""
    models: list[ModelConfig]
    config: SharedConfig = Field(default_factory=SharedConfig)
    documents: list[DocumentEntry]

    @classmethod
    def from_yaml(cls, path: Path) -> ExperimentManifest:
        """Load manifest from a YAML file."""
        with path.open() as f:
            data = yaml.safe_load(f)
        return cls.model_validate(data)


# -----------------------------------------------------------------------------
# Result Records
# -----------------------------------------------------------------------------


class RunRecord(BaseModel):
    """Record of a single classification run."""

    experiment: str
    timestamp: str
    document: str
    provider: str
    model: str
    latency_ms: int
    success: bool
    result: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None
    expected: dict[str, str]
    matches: dict[str, bool] | None = None
    all_match: bool = False


# -----------------------------------------------------------------------------
# Runner Logic
# -----------------------------------------------------------------------------

COMPARISON_FIELDS = ["domain", "category", "doctype", "vendor", "date", "subject"]

# Abbreviations for report table headers (avoid truncation)
FIELD_ABBREVS = {
    "domain": "Dom",
    "category": "Cat",
    "doctype": "Type",
    "vendor": "Vend",
    "date": "Date",
    "subject": "Subj",
}


_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STRICT_FIELDS = ("domain", "category", "doctype", "date")


def _tokens(value: str) -> set[str]:
    return set(_TOKEN_RE.findall(value.lower()))


def _normalized_vendor(value: str) -> str:
    return " ".join(_TOKEN_RE.findall(value.lower()))


def _subject_matches(predicted: str, expected: str) -> bool:
    """Token-set subset match: every expected token must appear in predicted."""
    expected_tokens = _tokens(expected)
    predicted_tokens = _tokens(predicted)
    if not expected_tokens:
        return not predicted_tokens
    return expected_tokens.issubset(predicted_tokens)


def compare_results(
    result: ClassificationResult, expected: ExpectedClassification
) -> dict[str, bool]:
    """Compare a classification result against expected ground truth.

    Comparison rules per field:
      - domain, category, doctype, date: strict equality (canonical / structured).
      - vendor: case-folded, punctuation-stripped, whitespace-collapsed.
      - subject: token-set subset match (predicted must contain every token
        from expected). Token-based matching cannot bridge semantically
        related but lexically disjoint subjects (e.g. "medical services" vs
        "office visit lab tests"); embedding-based similarity would be a
        future enhancement.
    """
    matches: dict[str, bool] = {
        field: getattr(result, field) == getattr(expected, field)
        for field in _STRICT_FIELDS
    }
    matches["vendor"] = _normalized_vendor(result.vendor) == _normalized_vendor(
        expected.vendor
    )
    matches["subject"] = _subject_matches(result.subject, expected.subject)
    return {field: matches[field] for field in COMPARISON_FIELDS}


async def run_single_classification(
    doc_entry: DocumentEntry,
    model_config: ModelConfig,
    shared_config: SharedConfig,
    experiment_name: str,
) -> RunRecord:
    """Run classification for a single document with a single model."""
    config = DroverConfig(
        ai=AIConfig(
            provider=model_config.provider,
            model=model_config.model,
            max_tokens=shared_config.max_tokens,
        ),
        taxonomy=shared_config.taxonomy,
        taxonomy_mode=shared_config.taxonomy_mode,
        sample_strategy=shared_config.sample_strategy,
        max_pages=shared_config.max_pages,
        prompt=shared_config.prompt,
        capture_debug=shared_config.capture_debug,
        debug_dir=shared_config.debug_dir,
    )

    service = ClassificationService(config)

    start_time = time.perf_counter()
    result = await service.classify_file(doc_entry.path)
    elapsed_ms = int((time.perf_counter() - start_time) * 1000)

    timestamp = datetime.now(UTC).isoformat()
    expected_dict = doc_entry.expected.model_dump()

    if isinstance(result, ClassificationErrorResult):
        return RunRecord(
            experiment=experiment_name,
            timestamp=timestamp,
            document=str(doc_entry.path),
            provider=model_config.provider.value,
            model=model_config.model,
            latency_ms=elapsed_ms,
            success=False,
            error_code=result.error_code.value,
            error_message=result.error_message,
            expected=expected_dict,
            matches=None,
            all_match=False,
        )

    matches = compare_results(result, doc_entry.expected)
    all_match = all(matches.values())

    return RunRecord(
        experiment=experiment_name,
        timestamp=timestamp,
        document=str(doc_entry.path),
        provider=model_config.provider.value,
        model=model_config.model,
        latency_ms=elapsed_ms,
        success=True,
        result={
            "domain": result.domain,
            "category": result.category,
            "doctype": result.doctype,
            "vendor": result.vendor,
            "date": result.date,
            "subject": result.subject,
            "suggested_path": result.suggested_path,
        },
        expected=expected_dict,
        matches=matches,
        all_match=all_match,
    )


async def run_experiment(
    manifest: ExperimentManifest,
    output_path: Path,
    verbose: bool = False,
) -> list[RunRecord]:
    """Run the full experiment matrix and write results to JSONL."""
    records: list[RunRecord] = []
    total_runs = len(manifest.documents) * len(manifest.models)
    current_run = 0
    experiment_start = time.perf_counter()

    with output_path.open("w") as f:
        for doc_entry in manifest.documents:
            for model_config in manifest.models:
                current_run += 1

                # Calculate ETA based on average time per completed run
                if verbose:
                    eta_str = ""
                    if current_run > 1:
                        elapsed = time.perf_counter() - experiment_start
                        avg_per_run = elapsed / (current_run - 1)
                        remaining = (total_runs - current_run + 1) * avg_per_run
                        eta_str = f" ETA: {int(remaining)}s"

                    model_str = f"{model_config.provider.value}/{model_config.model}"
                    progress = f"[{current_run}/{total_runs}]{eta_str}"
                    click.echo(
                        f"{progress} {doc_entry.path.name} + {model_str}", err=True
                    )

                try:
                    record = await run_single_classification(
                        doc_entry, model_config, manifest.config, manifest.name
                    )
                except Exception as e:
                    # Create error record for unexpected failures
                    record = RunRecord(
                        experiment=manifest.name,
                        timestamp=datetime.now(UTC).isoformat(),
                        document=str(doc_entry.path),
                        provider=model_config.provider.value,
                        model=model_config.model,
                        latency_ms=0,
                        success=False,
                        error_code="UNEXPECTED_ERROR",
                        error_message=f"{type(e).__name__}: {e}",
                        expected=doc_entry.expected.model_dump(),
                        matches=None,
                        all_match=False,
                    )

                records.append(record)

                # Write record immediately (streaming output)
                f.write(record.model_dump_json() + "\n")
                f.flush()

                if verbose:
                    status = (
                        "PASS"
                        if record.all_match
                        else ("FAIL" if record.success else "ERROR")
                    )
                    click.echo(f"    -> {status} ({record.latency_ms}ms)", err=True)

    return records


# -----------------------------------------------------------------------------
# Report Generation
# -----------------------------------------------------------------------------


def load_results(path: Path) -> list[RunRecord]:
    """Load results from a JSONL file."""
    records = []
    with path.open() as f:
        for line in f:
            if line.strip():
                records.append(RunRecord.model_validate_json(line))
    return records


def generate_report(records: list[RunRecord]) -> str:
    """Generate a summary report from run records."""
    if not records:
        return "No results to report."

    lines = []
    experiment_name = records[0].experiment

    # Extract experiment metadata
    models = sorted({(r.provider, r.model) for r in records})
    documents = sorted({r.document for r in records})
    successful = [r for r in records if r.success]
    failed = [r for r in records if not r.success]

    # Header
    lines.append("=" * 80)
    lines.append(f"Experiment: {experiment_name}")
    if records:
        lines.append(f"Run: {records[0].timestamp[:19].replace('T', ' ')}")
    lines.append("=" * 80)
    lines.append("")

    # Overview
    lines.append("Overview:")
    lines.append(f"  Documents: {len(documents)}")
    lines.append(f"  Models: {len(models)}")
    lines.append(f"  Total runs: {len(records)}")
    lines.append(f"  Successful: {len(successful)}")
    lines.append(f"  Failed: {len(failed)}")
    lines.append("")

    # Accuracy by model
    lines.append("-" * 80)
    lines.append("Accuracy by Model (% of fields correct across all documents)")
    lines.append("-" * 80)

    # Header row - 5 chars for abbrev + 1 for % = 6 total per column
    header = f"  {'Provider/Model':<40}"
    for field in COMPARISON_FIELDS:
        header += f" {FIELD_ABBREVS[field]:>5}%"
    header += "   ALL%"
    lines.append(header)

    for provider, model in models:
        model_records = [
            r for r in successful if r.provider == provider and r.model == model
        ]
        if not model_records:
            continue

        model_name = f"{provider}/{model}"
        row = f"  {model_name:<40}"
        for field in COMPARISON_FIELDS:
            correct = sum(
                1 for r in model_records if r.matches and r.matches.get(field, False)
            )
            pct = (correct / len(model_records) * 100) if model_records else 0
            row += f" {pct:>5.0f}%"

        all_correct = sum(1 for r in model_records if r.all_match)
        all_pct = (all_correct / len(model_records) * 100) if model_records else 0
        row += f" {all_pct:>5.0f}%"
        lines.append(row)

    lines.append("")

    # Accuracy by field
    lines.append("-" * 80)
    lines.append("Accuracy by Field (across all models)")
    lines.append("-" * 80)

    for field in COMPARISON_FIELDS:
        correct = sum(
            1 for r in successful if r.matches and r.matches.get(field, False)
        )
        total = len(successful)
        pct = (correct / total * 100) if total else 0
        lines.append(f"  {field:<12} {pct:>5.0f}% ({correct}/{total})")

    all_correct = sum(1 for r in successful if r.all_match)
    all_pct = (all_correct / len(successful) * 100) if successful else 0
    lines.append(f"  {'ALL':<12} {all_pct:>5.0f}% ({all_correct}/{len(successful)})")
    lines.append("")

    # Latency statistics by model
    lines.append("-" * 80)
    lines.append("Latency by Model (milliseconds)")
    lines.append("-" * 80)
    lines.append(
        f"  {'Provider/Model':<40} {'p50':>8} {'p95':>8} {'mean':>8} {'max':>8}"
    )

    for provider, model in models:
        model_runs = [
            r
            for r in records
            if r.provider == provider and r.model == model and r.success
        ]
        latencies = sorted(r.latency_ms for r in model_runs)
        if not latencies:
            continue

        n = len(latencies)
        p50 = latencies[n // 2] if n else 0
        p95_idx = min(int(n * 0.95), n - 1) if n else 0
        p95 = latencies[p95_idx] if n else 0
        mean = sum(latencies) // n if n else 0
        max_lat = max(latencies) if latencies else 0

        model_name = f"{provider}/{model}"
        lines.append(f"  {model_name:<40} {p50:>8} {p95:>8} {mean:>8} {max_lat:>8}")

    lines.append("")

    # Failures (classification errors)
    if failed:
        lines.append("-" * 80)
        lines.append("Failures (classification errors)")
        lines.append("-" * 80)
        for r in failed:
            lines.append(f"  {Path(r.document).name} + {r.provider}/{r.model}")
            lines.append(f"    Error: {r.error_code} - {r.error_message}")
        lines.append("")

    # Mismatches (wrong classifications)
    mismatches = [r for r in successful if not r.all_match]
    if mismatches:
        lines.append("-" * 80)
        lines.append("Mismatches (wrong classifications)")
        lines.append("-" * 80)
        for r in mismatches:
            lines.append(f"  {Path(r.document).name} + {r.provider}/{r.model}")
            if r.matches and r.result:
                for field in COMPARISON_FIELDS:
                    if not r.matches.get(field, True):
                        expected_val = r.expected.get(field, "?")
                        got_val = r.result.get(field, "?")
                        lines.append(
                            f"    {field}: expected={expected_val}, got={got_val}"
                        )
            lines.append("")

    lines.append("=" * 80)

    return "\n".join(lines)


def generate_json_report(records: list[RunRecord]) -> str:
    """Generate a JSON summary report from run records."""
    if not records:
        return json.dumps({"error": "No results to report"})

    models = sorted({(r.provider, r.model) for r in records})
    successful = [r for r in records if r.success]

    # Calculate accuracy by model
    model_accuracy = {}
    for provider, model in models:
        model_records = [
            r for r in successful if r.provider == provider and r.model == model
        ]
        if not model_records:
            continue

        key = f"{provider}/{model}"
        field_accuracy = {}
        for field in COMPARISON_FIELDS:
            correct = sum(
                1 for r in model_records if r.matches and r.matches.get(field, False)
            )
            field_accuracy[field] = correct / len(model_records) if model_records else 0

        all_correct = sum(1 for r in model_records if r.all_match)
        model_accuracy[key] = {
            "fields": field_accuracy,
            "all_match": all_correct / len(model_records) if model_records else 0,
            "total_runs": len(model_records),
        }

    # Calculate overall field accuracy
    field_accuracy = {}
    for field in COMPARISON_FIELDS:
        correct = sum(
            1 for r in successful if r.matches and r.matches.get(field, False)
        )
        field_accuracy[field] = correct / len(successful) if successful else 0

    all_correct = sum(1 for r in successful if r.all_match)

    report = {
        "experiment": records[0].experiment,
        "timestamp": records[0].timestamp,
        "summary": {
            "total_runs": len(records),
            "successful": len(successful),
            "failed": len(records) - len(successful),
            "all_match": all_correct,
            "all_match_rate": all_correct / len(successful) if successful else 0,
        },
        "accuracy_by_model": model_accuracy,
        "accuracy_by_field": field_accuracy,
    }

    return json.dumps(report, indent=2)


def generate_csv_report(records: list[RunRecord]) -> str:
    """Generate a CSV report from run records."""
    if not records:
        return "error,No results to report"

    lines = []
    # Header
    header = ["document", "provider", "model", "success", "latency_ms"]
    header.extend(f"match_{field}" for field in COMPARISON_FIELDS)
    header.append("all_match")
    lines.append(",".join(header))

    # Data rows
    for r in records:
        row = [
            Path(r.document).name,
            r.provider,
            r.model,
            str(r.success).lower(),
            str(r.latency_ms),
        ]
        for field in COMPARISON_FIELDS:
            if r.matches:
                row.append(str(r.matches.get(field, False)).lower())
            else:
                row.append("")
        row.append(str(r.all_match).lower())
        lines.append(",".join(row))

    return "\n".join(lines)


# -----------------------------------------------------------------------------
# Validation
# -----------------------------------------------------------------------------


def validate_manifest(manifest: ExperimentManifest) -> list[str]:
    """Validate a manifest and return list of issues."""
    issues = []

    # Check document paths exist
    for doc in manifest.documents:
        if not doc.path.exists():
            issues.append(f"Document not found: {doc.path}")

    # Check for duplicate documents
    paths = [str(d.path) for d in manifest.documents]
    seen = set()
    for p in paths:
        if p in seen:
            issues.append(f"Duplicate document: {p}")
        seen.add(p)

    # Check models are valid
    valid_providers = {p.value for p in AIProvider}
    for m in manifest.models:
        if m.provider.value not in valid_providers:
            issues.append(f"Invalid provider: {m.provider}")

    # Check prompt template path if specified
    if manifest.config.prompt is not None and not manifest.config.prompt.exists():
        issues.append(f"Prompt template not found: {manifest.config.prompt}")

    return issues


# -----------------------------------------------------------------------------
# CLI Commands
# -----------------------------------------------------------------------------


@click.group()
def cli() -> None:
    """Evaluation runner for drover classification experiments.

    Run experiments to compare model accuracy on test documents with
    known ground truth labels.

    \b
    Examples:
        python scripts/run_eval_experiments.py validate eval/experiment.yaml
        python scripts/run_eval_experiments.py run eval/experiment.yaml -v
        python scripts/run_eval_experiments.py report eval/results/experiment-*.jsonl
    """
    pass


@cli.command()
@click.argument("manifest_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output",
    "-o",
    type=click.Path(path_type=Path),
    help="Output JSONL path (default: eval/results/{name}-{timestamp}.jsonl)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show progress for each run")
@click.option("--dry-run", is_flag=True, help="Show what would run without executing")
def run(manifest_path: Path, output: Path | None, verbose: bool, dry_run: bool) -> None:
    """Run an evaluation experiment from a YAML manifest.

    Executes classification for each (document x model) combination and
    records results to a JSONL file for analysis.

    \b
    Example:
        python scripts/run_eval_experiments.py run eval/my-experiment.yaml -v
    """
    try:
        manifest = ExperimentManifest.from_yaml(manifest_path)
    except ValidationError as e:
        click.echo(f"Invalid manifest: {e}", err=True)
        sys.exit(1)

    # Validate before running
    issues = validate_manifest(manifest)
    if issues:
        click.echo("Manifest validation failed:", err=True)
        for issue in issues:
            click.echo(f"  - {issue}", err=True)
        sys.exit(1)

    # Determine output path
    if output is None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        results_dir = Path("eval/results")
        results_dir.mkdir(parents=True, exist_ok=True)
        output = results_dir / f"{manifest.name}-{timestamp}.jsonl"

    # Dry run mode - show what would run without executing
    if dry_run:
        total_runs = len(manifest.documents) * len(manifest.models)
        click.echo(f"Experiment: {manifest.name}", err=True)
        click.echo(f"Would run {total_runs} classifications:", err=True)
        click.echo("", err=True)
        for doc in manifest.documents:
            for model in manifest.models:
                click.echo(
                    f"  {doc.path.name} x {model.provider.value}/{model.model}",
                    err=True,
                )
        click.echo("", err=True)
        click.echo(f"Output would be: {output}", err=True)
        return

    output.parent.mkdir(parents=True, exist_ok=True)

    click.echo(f"Running experiment: {manifest.name}", err=True)
    click.echo(f"  Models: {len(manifest.models)}", err=True)
    click.echo(f"  Documents: {len(manifest.documents)}", err=True)
    click.echo(f"  Output: {output}", err=True)
    click.echo("", err=True)

    try:
        records = asyncio.run(run_experiment(manifest, output, verbose))
    except KeyboardInterrupt:
        click.echo("\n\nInterrupted! Partial results saved to:", err=True)
        click.echo(f"  {output}", err=True)
        click.echo("Generate partial report with:", err=True)
        click.echo(
            f"  python scripts/run_eval_experiments.py report {output}", err=True
        )
        sys.exit(130)  # Standard SIGINT exit code

    # Print summary
    successful = sum(1 for r in records if r.success)
    all_match = sum(1 for r in records if r.all_match)
    click.echo("", err=True)
    click.echo(
        f"Complete: {len(records)} runs, {successful} successful, {all_match} exact matches",
        err=True,
    )
    click.echo(f"Results written to: {output}", err=True)


@cli.command()
@click.argument("results_path", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["text", "json", "csv"], case_sensitive=False),
    default="text",
    help="Output format (default: text)",
)
def report(results_path: Path, output_format: str) -> None:
    """Generate a summary report from results.

    \b
    Output formats:
        text  - Human-readable summary with accuracy tables
        json  - Machine-readable JSON with accuracy metrics
        csv   - Per-run data for spreadsheet analysis
    """
    records = load_results(results_path)

    if output_format == "text":
        click.echo(generate_report(records))
    elif output_format == "json":
        click.echo(generate_json_report(records))
    elif output_format == "csv":
        click.echo(generate_csv_report(records))


@cli.command()
@click.argument("manifest_path", type=click.Path(exists=True, path_type=Path))
def validate(manifest_path: Path) -> None:
    """Validate an experiment manifest."""
    try:
        manifest = ExperimentManifest.from_yaml(manifest_path)
    except ValidationError as e:
        click.echo(f"Schema validation failed: {e}", err=True)
        sys.exit(1)

    issues = validate_manifest(manifest)
    if issues:
        click.echo("Validation issues:", err=True)
        for issue in issues:
            click.echo(f"  - {issue}", err=True)
        sys.exit(1)

    click.echo(f"Manifest valid: {manifest.name}")
    click.echo(f"  Models: {len(manifest.models)}")
    click.echo(f"  Documents: {len(manifest.documents)}")
    for doc in manifest.documents:
        status = "OK" if doc.path.exists() else "MISSING"
        click.echo(f"    [{status}] {doc.path}")


if __name__ == "__main__":
    cli()
