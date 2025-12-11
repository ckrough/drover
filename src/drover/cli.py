"""Drover CLI - Document classification command-line interface."""

import asyncio
import json
import sys
from pathlib import Path

import click
from rich.console import Console

from drover import __version__
from drover.config import (
    AIProvider,
    DroverConfig,
    ErrorMode,
    LogLevel,
    SampleStrategy,
    TaxonomyMode,
)
from drover.logging import configure_logging
from drover.models import ClassificationErrorResult as ClassificationErrorModel
from drover.models import ClassificationResult
from drover.service import ClassificationService

console = Console(stderr=True)


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
        config = config.with_overrides(on_error=ErrorMode.CONTINUE if batch else ErrorMode.FAIL)

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
        console.print(f"[dim]Using {config.ai.provider} with model {config.ai.model}[/dim]")
        console.print(f"[dim]Prompt template: {prompt_source}[/dim]")
    if log == LogLevel.DEBUG:
        console.print(f"[dim]Debug: Processing {len(files)} file(s)[/dim]")
        console.print(f"[dim]Debug: Provider={config.ai.provider}, Model={config.ai.model}[/dim]")
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


if __name__ == "__main__":
    main()
