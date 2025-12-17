#!/usr/bin/env python3
"""Batch organize script: classify, rename, and tag files.

Recursively scans a directory, classifies all files using drover's batch mode,
renames them to the suggested filename (in-place), and tags them with
domain, category, and doctype metadata.

Usage:
    python scripts/batch_organize.py /path/to/directory --config drover.yaml
    python scripts/batch_organize.py ~/Documents --config ~/.config/drover/config.yaml --dry-run
    python scripts/batch_organize.py ./inbox --config drover.yaml -v
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import click


def discover_files(directory: Path) -> list[Path]:
    """Recursively find all files in a directory.

    Args:
        directory: Root directory to scan.

    Returns:
        List of file paths (excludes directories and hidden files).
    """
    files = []
    for path in directory.rglob("*"):
        # Skip directories
        if not path.is_file():
            continue
        # Skip hidden files and files in hidden directories
        if any(part.startswith(".") for part in path.parts):
            continue
        files.append(path)
    return sorted(files)


def classify_files(
    files: list[Path],
    config_path: Path,
    verbose: bool = False,
) -> dict[Path, dict]:
    """Classify files using drover's batch mode.

    Args:
        files: List of file paths to classify.
        config_path: Path to drover config file.
        verbose: Whether to show verbose output.

    Returns:
        Dictionary mapping original file paths to classification results.
    """
    if not files:
        return {}

    # Build drover classify command
    cmd = [
        "drover",
        "classify",
        *[str(f) for f in files],
        "--batch",
        "--config",
        str(config_path),
        "--on-error",
        "continue",
    ]

    if verbose:
        click.echo(f"Running: {' '.join(cmd[:6])}... ({len(files)} files)")

    result = subprocess.run(cmd, capture_output=True, text=True)

    # Parse JSONL output
    results: dict[Path, dict] = {}
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            data = json.loads(line)
            # Find the original file by matching the filename
            original_name = data.get("original", "")
            for f in files:
                if f.name == original_name:
                    results[f] = data
                    break
        except json.JSONDecodeError as e:
            if verbose:
                click.echo(f"Warning: Failed to parse JSON: {e}", err=True)

    return results


def get_unique_path(target: Path) -> Path:
    """Get a unique file path by adding numeric suffix if needed.

    Args:
        target: Desired target path.

    Returns:
        The target path if available, or a path with numeric suffix (-1, -2, etc.).
    """
    if not target.exists():
        return target

    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    counter = 1

    while True:
        candidate = parent / f"{stem}-{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def rename_file(
    source: Path,
    suggested_filename: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> Path | None:
    """Rename a file to the suggested filename (in-place).

    Args:
        source: Original file path.
        suggested_filename: New filename from classification.
        dry_run: If True, don't actually rename.
        verbose: Whether to show verbose output.

    Returns:
        New file path if renamed, None if skipped.
    """
    target = source.parent / suggested_filename
    target = get_unique_path(target)

    # Skip if source and target are the same
    if source == target:
        if verbose:
            click.echo("  -> Skipped: already named correctly")
        return source

    if dry_run:
        click.echo(f"  -> Would rename to: {target.name}")
        return target

    try:
        source.rename(target)
        click.echo(f"  -> Renamed to: {target.name}")
        return target
    except OSError as e:
        click.echo(f"  -> Error renaming: {e}", err=True)
        return None


def tag_file(
    file_path: Path,
    domain: str,
    category: str,
    doctype: str,
    config_path: Path,
    dry_run: bool = False,
    verbose: bool = False,
) -> bool:
    """Tag a file with domain, category, and doctype.

    Uses drover's tag command to apply macOS filesystem tags.

    Args:
        file_path: Path to file to tag.
        domain: Domain classification.
        category: Category classification.
        doctype: Document type classification.
        config_path: Path to drover config file.
        dry_run: If True, don't actually tag.
        verbose: Whether to show verbose output.

    Returns:
        True if tagging succeeded, False otherwise.
    """
    # Import TagManager directly to avoid re-classification overhead
    try:
        sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
        from drover.actions.tag import TagManager

        manager = TagManager()
        tags = [domain, category, doctype]

        if dry_run:
            click.echo(f"  -> Would tag: {', '.join(tags)}")
            return True

        manager.add_tags(file_path, tags)
        click.echo(f"  -> Tagged: {', '.join(tags)}")
        return True

    except ImportError:
        # Fall back to drover CLI if import fails
        if verbose:
            click.echo("  -> Using drover tag command (fallback)")

        cmd = [
            "drover",
            "tag",
            str(file_path),
            "--tag-fields",
            "domain,category,doctype",
            "--config",
            str(config_path),
        ]

        if dry_run:
            cmd.append("--dry-run")
            click.echo(f"  -> Would tag: domain={domain}, category={category}, doctype={doctype}")
            return True

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode == 0:
            click.echo(f"  -> Tagged: domain={domain}, category={category}, doctype={doctype}")
            return True
        else:
            click.echo(f"  -> Error tagging: {result.stderr}", err=True)
            return False

    except Exception as e:
        click.echo(f"  -> Error tagging: {e}", err=True)
        return False


@click.command()
@click.argument(
    "directory",
    type=click.Path(exists=True, file_okay=False, dir_okay=True, path_type=Path),
)
@click.option(
    "--config",
    "-c",
    "config_path",
    required=True,
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    help="Path to drover config file.",
)
@click.option(
    "--dry-run",
    is_flag=True,
    default=False,
    help="Preview changes without applying them.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    default=False,
    help="Show detailed output.",
)
def main(
    directory: Path,
    config_path: Path,
    dry_run: bool,
    verbose: bool,
) -> None:
    """Classify, rename, and tag files in a directory.

    Recursively scans DIRECTORY for files, classifies them using drover,
    renames them to the suggested filename (in-place), and applies
    domain/category/doctype tags.
    """
    click.echo(f"Scanning {directory}...")

    # Discover files
    files = discover_files(directory)
    if not files:
        click.echo("No files found.")
        return

    click.echo(f"Found {len(files)} files to process")
    if dry_run:
        click.echo("(dry-run mode - no changes will be made)\n")
    else:
        click.echo()

    # Classify all files in batch
    click.echo("Classifying files...")
    results = classify_files(files, config_path, verbose)
    click.echo(f"Classified {len(results)} files\n")

    # Process each file
    renamed_count = 0
    tagged_count = 0
    skipped_count = 0

    for i, file_path in enumerate(files, 1):
        click.echo(f"[{i}/{len(files)}] {file_path.name}")

        # Get classification result
        result = results.get(file_path)
        if not result or result.get("error"):
            if result:
                error_msg = result.get("error_message", "Classification failed")
            else:
                error_msg = "No result"
            click.echo(f"  -> Skipped: {error_msg}")
            skipped_count += 1
            continue

        # Show classification
        if verbose:
            click.echo(f"  -> Classified: {result.get('suggested_path', 'N/A')}")

        # Rename file
        suggested_filename = result.get("suggested_filename")
        if suggested_filename:
            new_path = rename_file(file_path, suggested_filename, dry_run, verbose)
            if new_path and new_path != file_path:
                renamed_count += 1
                file_path = new_path  # Update path for tagging
            elif new_path is None:
                skipped_count += 1
                continue

        # Tag file
        domain = result.get("domain", "")
        category = result.get("category", "")
        doctype = result.get("doctype", "")

        if domain and category and doctype:
            if tag_file(file_path, domain, category, doctype, config_path, dry_run, verbose):
                tagged_count += 1

    # Summary
    click.echo("\n" + "=" * 40)
    click.echo("Summary:")
    click.echo(f"  Processed: {len(files)} files")
    click.echo(f"  Renamed:   {renamed_count} files")
    click.echo(f"  Tagged:    {tagged_count} files")
    click.echo(f"  Skipped:   {skipped_count} files")

    if dry_run:
        click.echo("\n(dry-run mode - no changes were made)")


if __name__ == "__main__":
    main()
