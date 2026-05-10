"""Drover CLI - Document classification command-line interface."""

from __future__ import annotations

import asyncio
import json
import subprocess  # nosec B404 - fixed-argv invocations only
import sys
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any

import click
from rich.console import Console

from drover import __version__
from drover.actions import (
    ActionPlan,
    ActionResult,
    ActionRunner,
    MoveAction,
    MoveStatus,
    TagAction,
    TagMode,
    extract_tag_value,
)
from drover.config import (
    AIProvider,
    DroverConfig,
    ErrorMode,
    LogLevel,
    TaxonomyMode,
)
from drover.loader import SUPPORTED_EXTENSIONS
from drover.logging import configure_logging, get_logger
from drover.models import ClassificationErrorResult, ClassificationResult
from drover.sampling import SampleStrategy
from drover.service import ClassificationService, make_filename_matcher, walk_directory

if TYPE_CHECKING:
    from collections.abc import Callable

logger = get_logger(__name__)

console = Console(stderr=True)


def _git_head_marker() -> str:
    """Return short HEAD with `-dirty` suffix when the working tree has changes.

    Returns an empty string when not inside a git repository or when git is
    unavailable, so callers can record a best-effort provenance stamp without
    failing the eval run.
    """
    try:
        head = subprocess.check_output(  # nosec B603 B607 - fixed argv, trusted PATH
            ["git", "rev-parse", "--short", "HEAD"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return ""
    try:
        dirty = (
            subprocess.run(  # nosec B603 B607
                ["git", "diff", "--quiet"],
                check=False,
                stderr=subprocess.DEVNULL,
            ).returncode
            != 0
        )
    except (FileNotFoundError, OSError):
        dirty = False
    return f"{head}-dirty" if dirty else head


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
    "--debug-structure",
    is_flag=True,
    help="Dump DoclingDocument JSON to debug-dir.",
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
    debug_structure: bool,
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
        debug_structure=debug_structure,
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

    def handle_result(result: ClassificationResult | ClassificationErrorResult) -> None:
        """Emit one classification record to stdout, plus a verbose-mode confirmation."""
        _output_result(result, batch)
        if log == LogLevel.VERBOSE and not result.error:
            console.print(f"[green]✓[/green] Processed {result.original}")

    exit_code = await service.classify_files(list(files), on_result=handle_result)
    return exit_code


def _output_result(
    result: ClassificationResult | ClassificationErrorResult,
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
VALID_TAG_FIELDS = {
    "domain",
    "category",
    "doctype",
    "vendor",
    "date",
    "subject",
    "entity",
}


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
        runner = ActionRunner(config, [action])
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

        drover evaluate --ground-truth eval/ground_truth/synthetic.jsonl --ai-model gpt-4o
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
    from drover.evaluation import ClassificationEvaluator

    configure_logging(log)

    try:
        config = DroverConfig.load(config_path)
    except Exception as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]Configuration error: {e}[/red]")
        return 2

    # Apply CLI overrides via config so ClassificationService owns all construction.
    config = config.with_overrides(
        ai_provider=ai_provider,
        ai_model=ai_model,
        taxonomy=taxonomy_name,
    )

    if log != LogLevel.QUIET:
        console.print(
            f"[blue]Evaluating with {config.ai.provider.value}/{config.ai.model}...[/blue]"
        )

    try:
        service = ClassificationService(config)
    except ValueError as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]Configuration error: {e}[/red]")
        return 2

    try:
        evaluator = ClassificationEvaluator(
            ground_truth_path=ground_truth_path,
            documents_dir=documents_dir,
        )
    except FileNotFoundError as e:
        if log != LogLevel.QUIET:
            console.print(f"[red]{e}[/red]")
        return 1

    results = await evaluator.evaluate(service._classifier, service._loader)
    results.commit_hash = _git_head_marker()

    if output_format == "json":
        click.echo(json.dumps(results.to_dict(), indent=2))
    else:
        console.print(results.summary())

    # Return non-zero if accuracy is poor (useful for CI)
    if results.domain_accuracy < 0.5:
        return 1
    return 0


@main.command()
@click.argument(
    "src",
    type=click.Path(exists=True, path_type=Path, resolve_path=True),
)
@click.option(
    "--dest",
    "dest_root",
    required=True,
    type=click.Path(file_okay=False, path_type=Path),
    help="Destination root for the organized tree (required).",
)
@click.option(
    "--copy",
    "copy_mode",
    is_flag=True,
    default=False,
    help="Copy instead of move; source is preserved.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Plan without performing filesystem mutations.",
)
@click.option(
    "--tag-fields",
    "tag_fields_str",
    default=None,
    help=(
        "Comma-separated classification fields to apply as macOS Finder tags. "
        "Omit to skip tagging. Allowed: domain, category, doctype, vendor, date, subject."
    ),
)
@click.option(
    "--tag-mode",
    type=click.Choice([m.value for m in TagMode]),
    default=TagMode.ADD.value,
    help="How to apply tags relative to existing tags (only honored with --tag-fields).",
)
@click.option(
    "--report",
    "report_path",
    default=None,
    help="Path for JSONL report. Use '-' to stream to stdout.",
)
@click.option(
    "--follow-symlinks",
    is_flag=True,
    default=False,
    help="Descend into symlinked directories when SRC is a directory.",
)
@click.option(
    "--no-entity",
    "no_entity",
    is_flag=True,
    default=False,
    help=(
        "Suppress the entity slot in generated filenames. Reproduces the legacy"
        " 4-component pattern doctype-vendor-subject-YYYYMMDD."
    ),
)
@classification_options
def organize(
    src: Path,
    dest_root: Path,
    copy_mode: bool,
    dry_run: bool,
    tag_fields_str: str | None,
    tag_mode: str,
    report_path: str | None,
    follow_symlinks: bool,
    no_entity: bool,
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
) -> None:
    """Classify, optionally tag, and move files into a destination tree.

    SRC may be a single file or a directory. Each supported file is
    classified, optionally tagged, and moved (or copied with --copy) to
    {DEST}/{domain}/{category}/{doctype}/{filename}. Destination
    collisions are skipped (source untouched). Unsupported extensions
    are reported as soft notices and do not raise the exit code.

    Examples:

        # Move every file in ~/Downloads into the filed tree.
        drover organize ~/Downloads --dest ~/Documents/filed

        # Single-file flow for a Hazel rule or Folder Action.
        drover organize ~/Inbox/scan.pdf --dest ~/Documents/filed \\
            --tag-fields category,doctype --report ~/Library/Logs/drover/run.jsonl

        # Dry-run preview to stdout.
        drover organize ./inbox --dest /tmp/filed --dry-run --report -
    """
    tag_fields: list[str] | None = None
    if tag_fields_str is not None:
        tag_fields = [f.strip() for f in tag_fields_str.split(",") if f.strip()]
        invalid = set(tag_fields) - VALID_TAG_FIELDS
        if invalid:
            raise click.UsageError(
                f"Invalid tag fields: {sorted(invalid)}. "
                f"Valid fields: {', '.join(sorted(VALID_TAG_FIELDS))}"
            )
        if not tag_fields:
            raise click.UsageError("--tag-fields requires at least one field.")
        if sys.platform != "darwin":
            raise click.UsageError(
                "--tag-fields requires macOS (filesystem tags use macOS xattrs)."
            )

    dest_root = dest_root.expanduser().resolve()
    if dest_root.exists() and not dest_root.is_dir():
        raise click.UsageError(f"--dest must be a directory: {dest_root}")
    try:
        dest_root.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise click.UsageError(f"--dest is not writable: {dest_root} ({exc})") from exc

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

    if no_entity:
        config = config.with_overrides(naming_emit_entity=False)

    if on_error is None:
        default_mode = ErrorMode.CONTINUE if src.is_dir() else ErrorMode.FAIL
        config = config.with_overrides(on_error=default_mode)

    configure_logging(level=config.log_level, json_output=True)

    exit_code = asyncio.run(
        _organize(
            src=src,
            dest_root=dest_root,
            copy_mode=copy_mode,
            dry_run=dry_run,
            tag_fields=tag_fields,
            tag_mode_value=TagMode(tag_mode),
            report_path=report_path,
            follow_symlinks=follow_symlinks,
            config=config,
        )
    )
    sys.exit(exit_code)


async def _organize(
    src: Path,
    dest_root: Path,
    copy_mode: bool,
    dry_run: bool,
    tag_fields: list[str] | None,
    tag_mode_value: TagMode,
    report_path: str | None,
    follow_symlinks: bool,
    config: DroverConfig,
) -> int:
    """Run the organize pipeline for SRC."""
    if src.is_file():
        all_files: list[tuple[Path, bool]] = [
            (src, src.suffix.lower() in SUPPORTED_EXTENSIONS)
        ]
    elif src.is_dir():
        all_files = list(walk_directory(src, SUPPORTED_EXTENSIONS, follow_symlinks))
    else:
        click.echo(f"SRC is not a file or directory: {src}", err=True)
        return 2

    supported = [p for p, ok in all_files if ok]
    unsupported = [p for p, ok in all_files if not ok]

    counts = {"moved": 0, "skipped_exists": 0, "error": 0, "skipped_unsupported": 0}
    report_writer = _ReportWriter(report_path)

    logger.info(
        "organize_started",
        src=str(src),
        dest=str(dest_root),
        total=len(all_files),
        supported=len(supported),
        unsupported=len(unsupported),
        dry_run=dry_run,
        copy=copy_mode,
    )

    with report_writer:
        for unsup in unsupported:
            counts["skipped_unsupported"] += 1
            logger.info("organize_unsupported", file=str(unsup))
            report_writer.write(
                _build_organize_record(
                    original_path=unsup,
                    suggested_path=None,
                    final_destination=None,
                    status=(
                        "would_skip_unsupported" if dry_run else "skipped_unsupported"
                    ),
                    tags_applied=[],
                    error=None,
                )
            )

        if not supported:
            logger.info("organize_complete", **counts)
            return _organize_exit_code(counts)

        try:
            service = ClassificationService(config)
        except ValueError as e:
            click.echo(f"Configuration error: {e}", err=True)
            return 2

        results_by_path = await _classify_for_organize(service, supported)

        move_action = MoveAction(dest_root=dest_root, copy=copy_mode)
        tag_action: TagAction | None = None
        if tag_fields:
            tag_action = TagAction(fields=tag_fields, mode=tag_mode_value)

        for file_path in supported:
            result = results_by_path.get(file_path)
            if result is None:
                counts["error"] += 1
                logger.info(
                    "organize_error",
                    file=str(file_path),
                    error="Classification produced no result",
                )
                report_writer.write(
                    _build_organize_record(
                        original_path=file_path,
                        suggested_path=None,
                        final_destination=None,
                        status=MoveStatus.ERROR.value,
                        tags_applied=[],
                        error="Classification produced no result",
                    )
                )
                continue

            if isinstance(result, ClassificationErrorResult) or result.error:
                err_msg = (
                    getattr(result, "error_message", None) or "Classification failed"
                )
                counts["error"] += 1
                logger.info(
                    "organize_error",
                    file=str(file_path),
                    error=str(err_msg),
                )
                report_writer.write(
                    _build_organize_record(
                        original_path=file_path,
                        suggested_path=None,
                        final_destination=None,
                        status=MoveStatus.ERROR.value,
                        tags_applied=[],
                        error=str(err_msg),
                    )
                )
                continue

            record = _organize_one(
                file_path=file_path,
                result=result,
                move_action=move_action,
                tag_action=tag_action,
                tag_fields=tag_fields,
                dry_run=dry_run,
                counts=counts,
            )
            report_writer.write(record)

    logger.info("organize_complete", **counts)
    return _organize_exit_code(counts)


async def _classify_for_organize(
    service: ClassificationService, files: list[Path]
) -> dict[Path, ClassificationResult | ClassificationErrorResult]:
    """Classify files and map results back to source paths.

    Files with duplicate basenames are matched in encounter order.
    """
    match_path = make_filename_matcher(files)
    results: dict[Path, ClassificationResult | ClassificationErrorResult] = {}

    def handle(
        result: ClassificationResult | ClassificationErrorResult,
    ) -> None:
        """Record the classification result against its source Path."""
        path = match_path(result.original)
        if path is not None:
            results[path] = result

    await service.classify_files(files, on_result=handle)
    return results


def _organize_one(
    file_path: Path,
    result: ClassificationResult,
    move_action: MoveAction,
    tag_action: TagAction | None,
    tag_fields: list[str] | None,
    dry_run: bool,
    counts: dict[str, int],
) -> dict[str, Any]:
    """Run move (and optional tag) for one classified file. Returns a report record."""
    move_plan = move_action.plan(file_path, result)

    if dry_run:
        status = move_plan.changes["status"]
        destination = move_plan.changes["destination"]
        if status == MoveStatus.WOULD_SKIP_EXISTS.value:
            counts["skipped_exists"] += 1
            logger.info(
                "organize_skipped_exists",
                file=str(file_path),
                destination=str(destination),
                status=status,
            )
            return _build_organize_record(
                original_path=file_path,
                suggested_path=result.suggested_path,
                final_destination=None,
                status=status,
                tags_applied=[],
                error=None,
            )
        counts["moved"] += 1
        tags_applied = _tag_field_records(result, tag_fields) if tag_fields else []
        logger.info(
            "organize_moved",
            file=str(file_path),
            destination=str(destination),
            status=status,
        )
        return _build_organize_record(
            original_path=file_path,
            suggested_path=result.suggested_path,
            final_destination=destination,
            status=status,
            tags_applied=tags_applied,
            error=None,
        )

    move_result = move_action.execute(move_plan)
    if not move_result.success:
        counts["error"] += 1
        logger.info(
            "organize_error",
            file=str(file_path),
            error=move_result.error or "Move failed",
        )
        return _build_organize_record(
            original_path=file_path,
            suggested_path=result.suggested_path,
            final_destination=None,
            status=MoveStatus.ERROR.value,
            tags_applied=[],
            error=move_result.error or "Move failed",
        )

    status = str(move_result.changes.get("status", ""))
    if status == MoveStatus.SKIPPED_EXISTS.value:
        counts["skipped_exists"] += 1
        logger.info(
            "organize_skipped_exists",
            file=str(file_path),
            destination=str(move_result.changes.get("destination", "")),
            status=status,
        )
        return _build_organize_record(
            original_path=file_path,
            suggested_path=result.suggested_path,
            final_destination=None,
            status=status,
            tags_applied=[],
            error=None,
        )

    counts["moved"] += 1
    final_dest = Path(str(move_result.changes["destination"]))
    logger.info(
        "organize_moved",
        file=str(file_path),
        destination=str(final_dest),
        status=status,
    )
    tags_applied = []
    if tag_action is not None and tag_fields:
        try:
            tag_plan = tag_action.plan(final_dest, result)
            tag_result = tag_action.execute(tag_plan)
            if tag_result.success:
                added = tag_result.changes.get("tags_added", []) or []
                tags_applied = _tag_field_records(
                    result, tag_fields, only_values=set(added)
                )
        except Exception as exc:
            logger.warning(
                "organize_tag_failed",
                file=str(final_dest),
                error=str(exc),
            )
    return _build_organize_record(
        original_path=file_path,
        suggested_path=result.suggested_path,
        final_destination=str(final_dest),
        status=status,
        tags_applied=tags_applied,
        error=None,
    )


def _tag_field_records(
    result: ClassificationResult,
    fields: list[str] | None,
    only_values: set[str] | None = None,
) -> list[dict[str, str]]:
    """Build the tags_applied record list from classification fields.

    Args:
        result: Classification result.
        fields: Field names to include.
        only_values: When provided, restrict to records whose value
            appears in this set (used in live mode to mirror what was
            actually written).
    """
    if not fields:
        return []
    records: list[dict[str, str]] = []
    for field in fields:
        value = extract_tag_value(result, field)
        if not value:
            continue
        if only_values is not None and value not in only_values:
            continue
        records.append({"field": field, "value": value})
    return records


def _build_organize_record(
    original_path: Path,
    suggested_path: str | None,
    final_destination: str | None,
    status: str,
    tags_applied: list[dict[str, str]],
    error: str | None,
) -> dict[str, Any]:
    """Build the canonical organize JSONL record."""
    return {
        "original_path": str(original_path),
        "suggested_path": suggested_path,
        "final_destination": final_destination,
        "status": status,
        "tags_applied": tags_applied,
        "error": error,
    }


def _organize_exit_code(counts: dict[str, int]) -> int:
    """Compute the organize exit code from per-status counters.

    skipped_unsupported is a soft notice and does not raise the exit
    code. Any error or skipped_exists yields exit 1; otherwise exit 0.
    """
    if counts.get("error", 0) > 0 or counts.get("skipped_exists", 0) > 0:
        return 1
    return 0


class _ReportWriter:
    """Context-managed writer for the organize JSONL report.

    None path → no-op. ``-`` → write to stdout. Anything else → open the
    file for writing and close on exit.
    """

    def __init__(self, path: str | None) -> None:
        self.path = path
        self._fp: IO[str] | None = None
        self._owns_fp = False

    def __enter__(self) -> _ReportWriter:
        if self.path is None:
            return self
        if self.path == "-":
            self._fp = sys.stdout
            return self
        target = Path(self.path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        self._fp = target.open("w", encoding="utf-8")
        self._owns_fp = True
        return self

    def __exit__(self, *_exc: object) -> None:
        if self._owns_fp and self._fp is not None:
            self._fp.close()
            self._fp = None

    def write(self, record: dict[str, Any]) -> None:
        """Append one JSONL record to the report sink, no-op when none configured."""
        if self._fp is None:
            return
        self._fp.write(json.dumps(record) + "\n")
        # Flush per record so a Hazel/Folder Action invocation that gets
        # killed mid-batch still has a complete audit log up to the last
        # processed file. The cost is one syscall per file, dominated by
        # the LLM round-trip in any realistic run.
        self._fp.flush()


if __name__ == "__main__":
    main()
