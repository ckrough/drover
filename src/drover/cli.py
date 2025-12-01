"""Drover CLI - Document classification command-line interface."""

import asyncio
import json
import sys
from pathlib import Path

import click
from rich.console import Console

from drover import __version__
from drover.classifier import (
    ClassificationError,
    DocumentClassifier,
    LLMParseError,
    TaxonomyValidationError,
)
from drover.config import (
    AIProvider,
    DroverConfig,
    ErrorMode,
    LogLevel,
    SampleStrategy,
    TaxonomyMode,
)
from drover.loader import DocumentLoader, DocumentLoadError
from drover.models import ClassificationError as ClassificationErrorModel
from drover.models import ClassificationResult, ErrorCode
from drover.naming import get_naming_policy
from drover.path_builder import PathBuilder
from drover.taxonomy import get_taxonomy

# Console for stderr output
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
    "--log-level",
    type=click.Choice([level.value for level in LogLevel]),
    help="Logging verbosity level.",
)
@click.option(
    "--batch",
    is_flag=True,
    help="Process multiple files, output JSONL.",
)
def classify(
    files: tuple[Path, ...],
    config_path: Path | None,
    ai_provider: str | None,
    ai_model: str | None,
    taxonomy_name: str | None,
    taxonomy_mode: str | None,
    naming_style: str | None,
    sample_strategy: str | None,
    max_pages: int | None,
    on_error: str | None,
    concurrency: int | None,
    metrics: bool,
    capture_debug: bool,
    log_level: str | None,
    batch: bool,
) -> None:
    """Classify documents and suggest organized file paths.

    FILES: One or more document files to classify.
    """
    if not files:
        raise click.UsageError("At least one file is required.")

    # Load configuration with precedence
    config = DroverConfig.load(config_path)

    # Apply CLI overrides
    config = config.with_overrides(
        ai_provider=ai_provider,
        ai_model=ai_model,
        taxonomy=taxonomy_name,
        taxonomy_mode=taxonomy_mode,
        naming_style=naming_style,
        sample_strategy=sample_strategy,
        max_pages=max_pages,
        on_error=on_error,
        concurrency=concurrency,
        metrics=metrics,
        capture_debug=capture_debug,
        log_level=log_level,
    )

    # Set error mode default based on batch
    if on_error is None:
        config = config.with_overrides(on_error=ErrorMode.CONTINUE if batch else ErrorMode.FAIL)

    # Run async classification
    exit_code = asyncio.run(_classify_files(files, config, batch))
    sys.exit(exit_code)


async def _classify_files(
    files: tuple[Path, ...],
    config: DroverConfig,
    batch: bool,
) -> int:
    """Classify files asynchronously.

    Args:
        files: Files to classify.
        config: Configuration.
        batch: Whether in batch mode.

    Returns:
        Exit code (0=success, 1=partial failure, 2=complete failure).
    """
    log = config.log_level

    if log == LogLevel.VERBOSE:
        console.print(f"[dim]Using {config.ai.provider} with model {config.ai.model}[/dim]")
    if log == LogLevel.DEBUG:
        console.print(f"[dim]Debug: Processing {len(files)} file(s)[/dim]")
        console.print(f"[dim]Debug: Provider={config.ai.provider}, Model={config.ai.model}[/dim]")

    # Initialize components
    try:
        taxonomy = get_taxonomy(config.taxonomy)
        naming_policy = get_naming_policy(config.naming_style)
    except ValueError as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]Configuration error: {e}[/red]")
        return 2

    loader = DocumentLoader(
        strategy=SampleStrategy(config.sample_strategy),
        max_pages=config.max_pages,
    )

    classifier = DocumentClassifier(
        provider=config.ai.provider,
        model=config.ai.model,
        taxonomy=taxonomy,
        taxonomy_mode=config.taxonomy_mode,
    )

    path_builder = PathBuilder(naming_policy=naming_policy)

    # Process files with concurrency control
    semaphore = asyncio.Semaphore(config.concurrency)
    results: list[ClassificationResult | ClassificationErrorModel] = []
    errors = 0

    async def process_file(file_path: Path) -> ClassificationResult | ClassificationErrorModel:
        async with semaphore:
            return await _classify_single_file(
                file_path=file_path,
                loader=loader,
                classifier=classifier,
                path_builder=path_builder,
                config=config,
            )

    tasks = [process_file(f) for f in files]

    for coro in asyncio.as_completed(tasks):
        result = await coro
        results.append(result)

        if isinstance(result, ClassificationErrorModel) or result.error:
            errors += 1
            if config.on_error == ErrorMode.FAIL:
                # Output error and exit
                _output_result(result, batch)
                return 2
            elif config.on_error == ErrorMode.SKIP:
                continue

        _output_result(result, batch)

        if log == LogLevel.VERBOSE and not (
            isinstance(result, ClassificationErrorModel) or result.error
        ):
            console.print(f"[green]✓[/green] Processed {result.original}")

    # Determine exit code
    if errors == len(files):
        return 2  # Complete failure
    elif errors > 0:
        return 1  # Partial failure
    return 0  # Success


async def _classify_single_file(
    file_path: Path,
    loader: DocumentLoader,
    classifier: DocumentClassifier,
    path_builder: PathBuilder,
    config: DroverConfig,
) -> ClassificationResult | ClassificationErrorModel:
    """Classify a single file.

    Args:
        file_path: Path to file.
        loader: Document loader.
        classifier: LLM classifier.
        path_builder: Path builder.
        config: Configuration.

    Returns:
        Classification result or error.
    """
    log = config.log_level

    try:
        # Load document
        if log == LogLevel.DEBUG:
            console.print(f"[dim]Debug: Loading {file_path.name}[/dim]")

        loaded = await loader.load(file_path)

        if log == LogLevel.DEBUG:
            console.print(
                f"[dim]Debug: Loaded {loaded.pages_sampled}/{loaded.page_count} pages[/dim]"
            )

        # Classify
        if log == LogLevel.DEBUG:
            console.print("[dim]Debug: Classifying...[/dim]")

        classification, debug_info = await classifier.classify(
            content=loaded.content,
            capture_debug=config.capture_debug,
        )

        # Save debug files if requested
        if config.capture_debug and debug_info:
            _save_debug_files(file_path, debug_info)

        # Build path
        result = path_builder.build(classification, file_path)

        return result

    except DocumentLoadError as e:
        return ClassificationErrorModel.from_exception(
            file_path.name, ErrorCode.DOCUMENT_LOAD_FAILED, e
        )
    except LLMParseError as e:
        return ClassificationErrorModel.from_exception(file_path.name, ErrorCode.LLM_PARSE_ERROR, e)
    except TaxonomyValidationError as e:
        return ClassificationErrorModel.from_exception(
            file_path.name, ErrorCode.TAXONOMY_VALIDATION_FAILED, e
        )
    except ClassificationError as e:
        return ClassificationErrorModel.from_exception(file_path.name, ErrorCode.LLM_API_ERROR, e)
    except Exception as e:
        return ClassificationErrorModel.from_exception(file_path.name, ErrorCode.LLM_API_ERROR, e)


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


def _save_debug_files(file_path: Path, debug_info: dict[str, str]) -> None:
    """Save debug information to files.

    Args:
        file_path: Original file path.
        debug_info: Debug info dict with 'prompt' and 'response' keys.
    """
    base = file_path.with_suffix("")

    if "prompt" in debug_info:
        prompt_file = base.with_suffix(".prompt.txt")
        prompt_file.write_text(debug_info["prompt"])

    if "response" in debug_info:
        response_file = base.with_suffix(".response.txt")
        response_file.write_text(debug_info["response"])


if __name__ == "__main__":
    main()
