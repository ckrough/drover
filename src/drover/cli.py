"""Drover CLI - Document classification command-line interface."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

import click
from rich.console import Console

from drover import __version__
from drover.actions import ActionPlan, ActionResult, ActionRunner, TagAction, TagMode
from drover.config import (
    AIProvider,
    DroverConfig,
    ErrorMode,
    LogLevel,
    TaxonomyMode,
)
from drover.logging import configure_logging
from drover.sampling import SampleStrategy
from drover.service import ClassificationService

if TYPE_CHECKING:
    from collections.abc import Callable

    from drover.models import ClassificationErrorResult as ClassificationErrorModel
    from drover.models import ClassificationResult

console = Console(stderr=True)


def classification_options(func: Callable[..., Any]) -> Callable[..., Any]:
    """Decorator that adds common classification CLI options."""
    decorators = [
        click.option(
            "--config",
            "config_path",
            type=click.Path(exists=True, path_type=Path),
            help="Path to configuration file.",
        ),
        click.option(
            "--ai-provider",
            type=click.Choice([p.value for p in AIProvider]),
            help="AI provider to use for classification.",
        ),
        click.option(
            "--ai-model",
            help="Model name for the AI provider.",
        ),
        click.option(
            "--ai-max-tokens",
            type=int,
            help="Maximum tokens in LLM response (default: 1000).",
        ),
        click.option(
            "--taxonomy",
            "taxonomy_name",
            help="Taxonomy to use for classification.",
        ),
        click.option(
            "--taxonomy-mode",
            type=click.Choice([m.value for m in TaxonomyMode]),
            help="How to handle unknown taxonomy values.",
        ),
        click.option(
            "--naming-style",
            help="Naming policy for generated filenames.",
        ),
        click.option(
            "--sample-strategy",
            type=click.Choice([s.value for s in SampleStrategy]),
            help="Document sampling strategy for large files.",
        ),
        click.option(
            "--max-pages",
            type=int,
            help="Maximum pages to process per document.",
        ),
        click.option(
            "--on-error",
            type=click.Choice([e.value for e in ErrorMode]),
            help="Error handling mode.",
        ),
        click.option(
            "--concurrency",
            type=int,
            help="Number of concurrent classification tasks.",
        ),
        click.option(
            "--log-level",
            type=click.Choice([level.value for level in LogLevel]),
            help="Logging verbosity level.",
        ),
    ]
    for decorator in reversed(decorators):
        func = decorator(func)
    return func


@click.group()
@click.version_option(version=__version__, prog_name="drover")
def main() -> None:
    """Drover - Document classification CLI that herds files into organized folders."""
    pass


@main.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file.",
)
@click.option(
    "--ai-provider",
    type=click.Choice([p.value for p in AIProvider]),
    help="AI provider to use for classification.",
)
@click.option(
    "--ai-model",
    help="Model name for the AI provider.",
)
@click.option(
    "--ai-max-tokens",
    type=int,
    help="Maximum tokens in LLM response (default: 1000).",
)
@click.option(
    "--taxonomy",
    "taxonomy_name",
    help="Taxonomy to use for classification.",
)
@click.option(
    "--taxonomy-mode",
    type=click.Choice([m.value for m in TaxonomyMode]),
    help="How to handle unknown taxonomy values.",
)
@click.option(
    "--naming-style",
    help="Naming policy for generated filenames.",
)
@click.option(
    "--sample-strategy",
    type=click.Choice([s.value for s in SampleStrategy]),
    help="Document sampling strategy for large files.",
)
@click.option(
    "--max-pages",
    type=int,
    help="Maximum pages to process per document.",
)
@click.option(
    "--on-error",
    type=click.Choice([e.value for e in ErrorMode]),
    help="Error handling mode.",
)
@click.option(
    "--concurrency",
    type=int,
    help="Number of concurrent classification tasks.",
)
@click.option(
    "--metrics",
    is_flag=True,
    help="Include AI metrics in output.",
)
@click.option(
    "--capture-debug",
    is_flag=True,
    help="Save prompts and responses to debug files.",
)
@click.option(
    "--debug-dir",
    "debug_dir",
    type=click.Path(file_okay=False, dir_okay=True, path_type=Path),
    help="Directory where debug prompt/response files are written.",
)
@click.option(
    "--log-level",
    type=click.Choice([level.value for level in LogLevel]),
    help="Logging verbosity level.",
)
@click.option(
    "--batch",
    is_flag=True,
    help="Process multiple files, output JSONL.",
)
@click.option(
    "--prompt",
    "prompt_path",
    type=click.Path(exists=True, path_type=Path),
    help="Custom prompt template file (Markdown with {taxonomy_menu}, {document_content}).",
)
def classify(
    files: tuple[Path, ...],
    config_path: Path | None,
    ai_provider: str | None,
    ai_model: str | None,
    ai_max_tokens: int | None,
    taxonomy_name: str | None,
    taxonomy_mode: str | None,
    naming_style: str | None,
    sample_strategy: str | None,
    max_pages: int | None,
    on_error: str | None,
    concurrency: int | None,
    metrics: bool,
    capture_debug: bool,
    debug_dir: Path | None,
    log_level: str | None,
    batch: bool,
    prompt_path: Path | None,
) -> None:
    """Classify documents and suggest organized file paths.

    FILES: One or more document files to classify.
    """
    if not files:
        raise click.UsageError("At least one file is required.")

    config = DroverConfig.load(config_path)
    config = config.with_overrides(
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_max_tokens=ai_max_tokens,
        taxonomy=taxonomy_name,
        taxonomy_mode=taxonomy_mode,
        naming_style=naming_style,
        sample_strategy=sample_strategy,
        max_pages=max_pages,
        on_error=on_error,
        concurrency=concurrency,
        metrics=metrics,
        capture_debug=capture_debug,
        debug_dir=debug_dir,
        log_level=log_level,
        prompt=prompt_path,
    )

    if on_error is None:
        config = config.with_overrides(
            on_error=ErrorMode.CONTINUE if batch else ErrorMode.FAIL
        )

    # Configure structured logging (JSON format by default)
    configure_logging(level=config.log_level, json_output=True)

    exit_code = asyncio.run(_classify_files(files, config, batch))
    sys.exit(exit_code)


async def _classify_files(
    files: tuple[Path, ...],
    config: DroverConfig,
    batch: bool,
) -> int:
    """Classify files asynchronously using ClassificationService.

    Args:
        files: Files to classify.
        config: Configuration.
        batch: Whether in batch mode.

    Returns:
        Exit code (0=success, 1=partial failure, 2=complete failure).
    """
    log = config.log_level
    prompt_source = str(config.prompt) if config.prompt else "default"

    if log == LogLevel.VERBOSE:
        console.print(
            f"[dim]Using {config.ai.provider} with model {config.ai.model}[/dim]"
        )
        console.print(f"[dim]Prompt template: {prompt_source}[/dim]")
    if log == LogLevel.DEBUG:
        console.print(f"[dim]Debug: Processing {len(files)} file(s)[/dim]")
        console.print(
            f"[dim]Debug: Provider={config.ai.provider}, Model={config.ai.model}[/dim]"
        )
        console.print(f"[dim]Debug: Prompt={prompt_source}[/dim]")

    try:
        service = ClassificationService(config)
    except ValueError as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]Configuration error: {e}[/red]")
        return 2

    def handle_result(result: ClassificationResult | ClassificationErrorModel) -> None:
        _output_result(result, batch)
        if log == LogLevel.VERBOSE and not result.error:
            console.print(f"[green]✓[/green] Processed {result.original}")

    exit_code = await service.classify_files(list(files), on_result=handle_result)
    return exit_code


def _output_result(
    result: ClassificationResult | ClassificationErrorModel,
    batch: bool,
) -> None:
    """Output classification result to stdout.

    Args:
        result: Classification result or error.
        batch: Whether in batch mode (JSONL).
    """
    data = result.model_dump(exclude_none=True)

    if batch:
        click.echo(json.dumps(data))
    else:
        click.echo(json.dumps(data, indent=2))


# Valid tag fields that can be extracted from classification results
VALID_TAG_FIELDS = {"domain", "category", "doctype", "vendor", "date", "subject"}


@main.command()
@click.argument("files", nargs=-1, type=click.Path(exists=True, path_type=Path))
@classification_options
@click.option(
    "--tag-fields",
    default="domain,category,doctype",
    help="Comma-separated fields to use as tags (default: domain,category,doctype).",
)
@click.option(
    "--tag-mode",
    type=click.Choice([m.value for m in TagMode]),
    default=TagMode.ADD.value,
    help="How to apply tags: replace, add, update, missing (default: add).",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what tags would be applied without making changes.",
)
def tag(
    files: tuple[Path, ...],
    config_path: Path | None,
    ai_provider: str | None,
    ai_model: str | None,
    ai_max_tokens: int | None,
    taxonomy_name: str | None,
    taxonomy_mode: str | None,
    naming_style: str | None,
    sample_strategy: str | None,
    max_pages: int | None,
    on_error: str | None,
    concurrency: int | None,
    log_level: str | None,
    tag_fields: str,
    tag_mode: str,
    dry_run: bool,
) -> None:
    """Classify documents and apply macOS filesystem tags.

    FILES: One or more document files to classify and tag.

    Tags are applied based on classification results. By default, the domain,
    category, and doctype fields are used as tags.

    Examples:

        # Tag files with default fields (domain, category, doctype)
        drover tag document.pdf

        # Tag with specific fields
        drover tag --tag-fields domain,vendor document.pdf

        # Preview tags without applying
        drover tag --dry-run document.pdf

        # Replace all existing tags
        drover tag --tag-mode replace document.pdf
    """
    if not files:
        raise click.UsageError("At least one file is required.")

    if sys.platform != "darwin":
        raise click.UsageError("The tag command is only supported on macOS.")

    # Parse and validate tag fields
    fields = [f.strip() for f in tag_fields.split(",")]
    invalid_fields = set(fields) - VALID_TAG_FIELDS
    if invalid_fields:
        raise click.UsageError(
            f"Invalid tag fields: {invalid_fields}. "
            f"Valid fields: {', '.join(sorted(VALID_TAG_FIELDS))}"
        )

    # Build configuration
    config = DroverConfig.load(config_path)
    config = config.with_overrides(
        ai_provider=ai_provider,
        ai_model=ai_model,
        ai_max_tokens=ai_max_tokens,
        taxonomy=taxonomy_name,
        taxonomy_mode=taxonomy_mode,
        naming_style=naming_style,
        sample_strategy=sample_strategy,
        max_pages=max_pages,
        on_error=on_error,
        concurrency=concurrency,
        log_level=log_level,
    )

    # Default to continue mode for batch tagging
    if on_error is None:
        config = config.with_overrides(on_error=ErrorMode.CONTINUE)

    configure_logging(level=config.log_level, json_output=True)

    exit_code = asyncio.run(
        _tag_files(files, config, fields, TagMode(tag_mode), dry_run)
    )
    sys.exit(exit_code)


async def _tag_files(
    files: tuple[Path, ...],
    config: DroverConfig,
    fields: list[str],
    mode: TagMode,
    dry_run: bool,
) -> int:
    """Tag files asynchronously using ActionRunner.

    Args:
        files: Files to tag.
        config: Configuration.
        fields: Fields to extract for tags.
        mode: Tag application mode.
        dry_run: Whether to only plan without executing.

    Returns:
        Exit code (0=success, 1=partial failure, 2=complete failure).
    """
    log = config.log_level

    if log == LogLevel.VERBOSE:
        console.print(
            f"[dim]Using {config.ai.provider} with model {config.ai.model}[/dim]"
        )
        console.print(f"[dim]Tag fields: {', '.join(fields)}[/dim]")
        console.print(f"[dim]Tag mode: {mode}[/dim]")
        if dry_run:
            console.print("[dim]Dry run mode - no changes will be made[/dim]")

    if log == LogLevel.DEBUG:
        console.print(f"[dim]Debug: Processing {len(files)} file(s)[/dim]")

    try:
        action = TagAction(fields=fields, mode=mode)
        runner = ActionRunner(config, action)
    except ValueError as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]Configuration error: {e}[/red]")
        return 2

    def handle_result(result: ActionPlan | ActionResult) -> None:
        _output_tag_result(result, log)

    exit_code = await runner.run(list(files), dry_run=dry_run, on_result=handle_result)
    return exit_code


def _output_tag_result(result: ActionPlan | ActionResult, log_level: LogLevel) -> None:
    """Output tag action result to stdout.

    Args:
        result: Action plan (dry-run) or result.
        log_level: Current logging level.
    """
    data = result.to_dict()
    click.echo(json.dumps(data))

    if log_level == LogLevel.VERBOSE:
        if isinstance(result, ActionResult):
            if result.success:
                console.print(f"[green]✓[/green] Tagged {result.file.name}")
            else:
                console.print(f"[red]✗[/red] Failed {result.file.name}: {result.error}")
        else:
            console.print(
                f"[blue]○[/blue] Would tag {result.file.name}: {result.description}"
            )


@main.command()
@click.option(
    "--ground-truth",
    "ground_truth_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to ground truth JSONL file.",
)
@click.option(
    "--documents-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing test documents. Defaults to ground_truth_dir/documents.",
)
@click.option(
    "--config",
    "config_path",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file.",
)
@click.option(
    "--ai-provider",
    type=click.Choice([p.value for p in AIProvider]),
    help="AI provider to use for classification.",
)
@click.option(
    "--ai-model",
    help="Model name for the AI provider.",
)
@click.option(
    "--taxonomy",
    "taxonomy_name",
    help="Taxonomy to use for classification.",
)
@click.option(
    "--output",
    "output_format",
    type=click.Choice(["summary", "json"]),
    default="summary",
    help="Output format (default: summary).",
)
@click.option(
    "--log",
    type=click.Choice([level.value for level in LogLevel]),
    default="quiet",
    help="Logging verbosity.",
)
def evaluate(
    ground_truth_path: Path,
    documents_dir: Path | None,
    config_path: Path | None,
    ai_provider: str | None,
    ai_model: str | None,
    taxonomy_name: str | None,
    output_format: str,
    log: str,
) -> None:
    """Evaluate classification accuracy against ground truth.

    Runs classification on test documents and compares results to
    expected values in the ground truth file. Outputs accuracy metrics
    for domain, category, and doctype classification.

    Example:

        drover evaluate --ground-truth eval/ground_truth.jsonl --ai-model gpt-4o
    """
    exit_code = asyncio.run(
        _evaluate_async(
            ground_truth_path=ground_truth_path,
            documents_dir=documents_dir,
            config_path=config_path,
            ai_provider=ai_provider,
            ai_model=ai_model,
            taxonomy_name=taxonomy_name,
            output_format=output_format,
            log=LogLevel(log),
        )
    )
    sys.exit(exit_code)


async def _evaluate_async(
    ground_truth_path: Path,
    documents_dir: Path | None,
    config_path: Path | None,
    ai_provider: str | None,
    ai_model: str | None,
    taxonomy_name: str | None,
    output_format: str,
    log: LogLevel,
) -> int:
    """Async implementation of evaluate command."""
    from drover.classifier import DocumentClassifier
    from drover.evaluation import ClassificationEvaluator
    from drover.loader import DocumentLoader
    from drover.taxonomy.loader import get_taxonomy

    configure_logging(log)

    try:
        config = DroverConfig.load(config_path)
    except Exception as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]Configuration error: {e}[/red]")
        return 2

    # Apply CLI overrides
    provider = AIProvider(ai_provider) if ai_provider else config.ai.provider
    model = ai_model or config.ai.model
    taxonomy_key = taxonomy_name or config.taxonomy

    if log != LogLevel.QUIET:
        console.print(f"[blue]Evaluating with {provider.value}/{model}...[/blue]")

    try:
        taxonomy = get_taxonomy(taxonomy_key)
    except ValueError as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]Taxonomy error: {e}[/red]")
        return 2

    classifier = DocumentClassifier(
        provider=provider,
        model=model,
        taxonomy=taxonomy,
        taxonomy_mode=config.taxonomy_mode,
        temperature=config.ai.temperature,
        max_tokens=config.ai.max_tokens,
        timeout=config.ai.timeout,
        max_retries=config.ai.max_retries,
        retry_min_wait=config.ai.retry_min_wait,
        retry_max_wait=config.ai.retry_max_wait,
    )

    loader = DocumentLoader(
        strategy=config.sample_strategy,
        max_pages=config.max_pages,
    )

    try:
        evaluator = ClassificationEvaluator(
            ground_truth_path=ground_truth_path,
            documents_dir=documents_dir,
        )
    except FileNotFoundError as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]{e}[/red]")
        return 1

    results = await evaluator.evaluate(classifier, loader=loader)

    if output_format == "json":
        click.echo(json.dumps(results.to_dict(), indent=2))
    else:
        console.print(results.summary())

    # Return non-zero if accuracy is poor (useful for CI)
    if results.domain_accuracy < 0.5:
        return 1
    return 0


if __name__ == "__main__":
    main()
