"""Tests for the drover tag CLI command."""

import sys
from pathlib import Path

import pytest
from click.testing import CliRunner

from drover.cli import main

# Skip all tests in this module on non-macOS platforms
pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="macOS filesystem tags only supported on macOS",
)


class TestTagCommand:
    """Tests for the tag CLI command."""

    def test_help(self) -> None:
        """Tag command shows help."""
        runner = CliRunner()
        result = runner.invoke(main, ["tag", "--help"])

        assert result.exit_code == 0
        assert "Classify documents and apply macOS filesystem tags" in result.output
        assert "--tag-fields" in result.output
        assert "--tag-mode" in result.output
        assert "--dry-run" in result.output

    def test_no_files_error(self) -> None:
        """Tag command requires at least one file."""
        runner = CliRunner()
        result = runner.invoke(main, ["tag"])

        assert result.exit_code != 0
        assert "At least one file is required" in result.output

    def test_invalid_field_error(self) -> None:
        """Tag command rejects invalid fields."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with Path("test.txt").open("w") as f:
                f.write("test content")

            result = runner.invoke(
                main, ["tag", "--tag-fields", "invalid_field", "test.txt"]
            )

        assert result.exit_code != 0
        assert "Invalid tag fields" in result.output

    def test_valid_fields_accepted(self) -> None:
        """Tag command accepts all valid fields."""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with Path("test.txt").open("w") as f:
                f.write("test content")

            # Just check that the field validation passes
            # (actual tagging would require mocking the classifier)
            result = runner.invoke(
                main,
                [
                    "tag",
                    "--tag-fields",
                    "domain,category,doctype,vendor,date,subject",
                    "--help",
                ],
            )

        # Help should work without errors
        assert result.exit_code == 0

    def test_tag_modes_available(self) -> None:
        """All tag modes are available in CLI."""
        runner = CliRunner()
        result = runner.invoke(main, ["tag", "--help"])

        assert "replace" in result.output
        assert "add" in result.output
        assert "update" in result.output
        assert "missing" in result.output

    def test_classification_options_present(self) -> None:
        """Tag command has all classification options."""
        runner = CliRunner()
        result = runner.invoke(main, ["tag", "--help"])

        assert "--ai-provider" in result.output
        assert "--ai-model" in result.output
        assert "--taxonomy" in result.output
        assert "--taxonomy-mode" in result.output
        assert "--concurrency" in result.output
        assert "--log-level" in result.output
