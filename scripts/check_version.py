#!/usr/bin/env python3
"""Validate version consistency between __init__.py and pyproject.toml.

This script ensures the version in src/agentspaces/__init__.py matches
the version in pyproject.toml to prevent version drift.

Exit codes:
    0: Versions match
    1: Version mismatch or error
"""

from __future__ import annotations

import re
import sys
import tomllib
from pathlib import Path


def get_init_version(init_file: Path) -> str | None:
    """Extract version from __init__.py file.

    Args:
        init_file: Path to __init__.py file.

    Returns:
        Version string if found, None otherwise.
    """
    content = init_file.read_text(encoding="utf-8")
    match = re.search(r'^__version__\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
    return match.group(1) if match else None


def get_pyproject_version(pyproject_file: Path) -> str | None:
    """Extract version from pyproject.toml file.

    Args:
        pyproject_file: Path to pyproject.toml file.

    Returns:
        Version string if found, None otherwise.
    """
    try:
        content = pyproject_file.read_text(encoding="utf-8")
        data = tomllib.loads(content)
        return data.get("project", {}).get("version")
    except (tomllib.TOMLDecodeError, KeyError):
        return None


def main() -> int:
    """Main validation logic.

    Returns:
        Exit code (0 for success, 1 for failure).
    """
    # Determine project root (script is in scripts/ directory)
    project_root = Path(__file__).parent.parent
    init_file = project_root / "src" / "agentspaces" / "__init__.py"
    pyproject_file = project_root / "pyproject.toml"

    # Check files exist
    if not init_file.exists():
        print(f"❌ Error: {init_file} not found", file=sys.stderr)
        return 1

    if not pyproject_file.exists():
        print(f"❌ Error: {pyproject_file} not found", file=sys.stderr)
        return 1

    # Extract versions
    init_version = get_init_version(init_file)
    if init_version is None:
        print(f"❌ Error: Could not find __version__ in {init_file}", file=sys.stderr)
        return 1

    pyproject_version = get_pyproject_version(pyproject_file)
    if pyproject_version is None:
        print(f"❌ Error: Could not find version in {pyproject_file}", file=sys.stderr)
        return 1

    # Compare versions
    if init_version != pyproject_version:
        print("❌ Version mismatch detected!", file=sys.stderr)
        print(f"   src/agentspaces/__init__.py: {init_version}", file=sys.stderr)
        print(f"   pyproject.toml:              {pyproject_version}", file=sys.stderr)
        print(file=sys.stderr)
        print("Please update both files to match.", file=sys.stderr)
        print("See RELEASING.md for version management guidelines.", file=sys.stderr)
        return 1

    # Success
    print(f"✅ Version consistency check passed: {init_version}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
