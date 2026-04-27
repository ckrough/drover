"""Tests for TagManager and tag operations."""

import sys
from pathlib import Path

import pytest

from drover.actions.tag import (
    TagAction,
    TagManager,
    TagMode,
    compute_final_tags,
    tags_from_result,
)
from drover.models import ClassificationResult

# Skip all tests in this module on non-macOS platforms
pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason="macOS filesystem tags only supported on macOS",
)


class TestTagManager:
    """Tests for TagManager xattr operations."""

    def test_init_on_macos(self) -> None:
        """TagManager initializes successfully on macOS."""
        manager = TagManager()
        assert manager is not None

    def test_read_tags_no_tags(self, tmp_path: Path) -> None:
        """Reading tags from file with no tags returns empty list."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        tags = manager.read_tags(test_file)

        assert tags == []

    def test_write_and_read_tags(self, tmp_path: Path) -> None:
        """Writing tags and reading them back works correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["financial", "banking"])
        tags = manager.read_tags(test_file)

        assert tags == ["financial", "banking"]

    def test_write_empty_tags_clears(self, tmp_path: Path) -> None:
        """Writing empty tag list clears existing tags."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["tag1", "tag2"])
        manager.write_tags(test_file, [])
        tags = manager.read_tags(test_file)

        assert tags == []

    def test_add_tags_to_existing(self, tmp_path: Path) -> None:
        """Adding tags preserves existing tags."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["existing"])
        manager.add_tags(test_file, ["new1", "new2"])
        tags = manager.read_tags(test_file)

        assert "existing" in tags
        assert "new1" in tags
        assert "new2" in tags

    def test_add_tags_no_duplicates(self, tmp_path: Path) -> None:
        """Adding duplicate tags doesn't create duplicates."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["tag1", "tag2"])
        manager.add_tags(test_file, ["tag2", "tag3"])
        tags = manager.read_tags(test_file)

        assert tags == ["tag1", "tag2", "tag3"]

    def test_remove_tags(self, tmp_path: Path) -> None:
        """Removing specific tags works correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["keep", "remove1", "remove2"])
        manager.remove_tags(test_file, ["remove1", "remove2"])
        tags = manager.read_tags(test_file)

        assert tags == ["keep"]

    def test_clear_tags(self, tmp_path: Path) -> None:
        """Clearing tags removes all tags."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["tag1", "tag2"])
        manager.clear_tags(test_file)
        tags = manager.read_tags(test_file)

        assert tags == []

    def test_unicode_tags(self, tmp_path: Path) -> None:
        """Unicode characters in tags work correctly."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["日本語", "émojis🎉", "über"])
        tags = manager.read_tags(test_file)

        assert tags == ["日本語", "émojis🎉", "über"]


class TestTagsFromResult:
    """Tests for tags_from_result helper function."""

    def _make_result(self, **kwargs) -> ClassificationResult:
        """Create a ClassificationResult with defaults."""
        defaults = {
            "original": "test.pdf",
            "suggested_path": "financial/banking/statement/test.pdf",
            "suggested_filename": "statement-chase-checking-20240315.pdf",
            "domain": "financial",
            "category": "banking",
            "doctype": "statement",
            "vendor": "chase",
            "date": "20240315",
            "subject": "checking account",
        }
        defaults.update(kwargs)
        return ClassificationResult(**defaults)

    def test_default_fields(self) -> None:
        """Default fields extract domain, category, doctype."""
        result = self._make_result()
        tags = tags_from_result(result, ["domain", "category", "doctype"])

        assert tags == ["financial", "banking", "statement"]

    def test_vendor_field(self) -> None:
        """Vendor field extracts correctly."""
        result = self._make_result(vendor="chase")
        tags = tags_from_result(result, ["vendor"])

        assert tags == ["chase"]

    def test_date_field_extracts_year(self) -> None:
        """Date field extracts only the year."""
        result = self._make_result(date="20240315")
        tags = tags_from_result(result, ["date"])

        assert tags == ["2024"]

    def test_empty_field_skipped(self) -> None:
        """Empty field values are skipped."""
        result = self._make_result(vendor="")
        tags = tags_from_result(result, ["domain", "vendor", "category"])

        assert tags == ["financial", "banking"]

    def test_all_fields(self) -> None:
        """All available fields work correctly."""
        result = self._make_result()
        tags = tags_from_result(
            result, ["domain", "category", "doctype", "vendor", "date"]
        )

        assert tags == ["financial", "banking", "statement", "chase", "2024"]


class TestComputeFinalTags:
    """Tests for compute_final_tags mode logic."""

    def test_replace_mode(self) -> None:
        """Replace mode replaces all existing tags."""
        result = compute_final_tags(
            existing=["old1", "old2"],
            new=["new1", "new2"],
            mode=TagMode.REPLACE,
        )

        assert result == ["new1", "new2"]

    def test_add_mode_appends(self) -> None:
        """Add mode appends new tags to existing."""
        result = compute_final_tags(
            existing=["existing"],
            new=["new1", "new2"],
            mode=TagMode.ADD,
        )

        assert result == ["existing", "new1", "new2"]

    def test_add_mode_no_duplicates(self) -> None:
        """Add mode doesn't create duplicate tags."""
        result = compute_final_tags(
            existing=["tag1", "tag2"],
            new=["tag2", "tag3"],
            mode=TagMode.ADD,
        )

        assert result == ["tag1", "tag2", "tag3"]

    def test_update_mode_with_existing_tags(self) -> None:
        """Update mode replaces when file has tags."""
        result = compute_final_tags(
            existing=["old"],
            new=["new1", "new2"],
            mode=TagMode.UPDATE,
        )

        assert result == ["new1", "new2"]

    def test_update_mode_without_existing_tags(self) -> None:
        """Update mode makes no changes when file has no tags."""
        result = compute_final_tags(
            existing=[],
            new=["new1", "new2"],
            mode=TagMode.UPDATE,
        )

        assert result == []

    def test_missing_mode_without_existing_tags(self) -> None:
        """Missing mode adds tags when file has none."""
        result = compute_final_tags(
            existing=[],
            new=["new1", "new2"],
            mode=TagMode.MISSING,
        )

        assert result == ["new1", "new2"]

    def test_missing_mode_with_existing_tags(self) -> None:
        """Missing mode makes no changes when file has tags."""
        result = compute_final_tags(
            existing=["old"],
            new=["new1", "new2"],
            mode=TagMode.MISSING,
        )

        assert result == ["old"]


class TestTagAction:
    """Tests for TagAction implementation."""

    def _make_result(self, **kwargs) -> ClassificationResult:
        """Create a ClassificationResult with defaults."""
        defaults = {
            "original": "test.pdf",
            "suggested_path": "financial/banking/statement/test.pdf",
            "suggested_filename": "statement-chase-checking-20240315.pdf",
            "domain": "financial",
            "category": "banking",
            "doctype": "statement",
            "vendor": "chase",
            "date": "20240315",
            "subject": "checking account",
        }
        defaults.update(kwargs)
        return ClassificationResult(**defaults)

    def test_plan_generates_correct_changes(self, tmp_path: Path) -> None:
        """Plan correctly computes tag changes."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        action = TagAction(fields=["domain", "category"], mode=TagMode.ADD)
        result = self._make_result()
        plan = action.plan(test_file, result)

        assert plan.file == test_file
        assert plan.changes["tags_added"] == ["financial", "banking"]
        assert plan.changes["tags_removed"] == []

    def test_plan_with_existing_tags(self, tmp_path: Path) -> None:
        """Plan accounts for existing tags."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["existing"])

        action = TagAction(fields=["domain"], mode=TagMode.ADD)
        result = self._make_result()
        plan = action.plan(test_file, result)

        assert plan.changes["existing_tags"] == ["existing"]
        assert plan.changes["tags_added"] == ["financial"]
        assert "existing" in plan.changes["final_tags"]
        assert "financial" in plan.changes["final_tags"]

    def test_execute_applies_tags(self, tmp_path: Path) -> None:
        """Execute applies the planned tags."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        action = TagAction(fields=["domain", "category"], mode=TagMode.ADD)
        result = self._make_result()

        plan = action.plan(test_file, result)
        action_result = action.execute(plan)

        assert action_result.success is True

        manager = TagManager()
        tags = manager.read_tags(test_file)
        assert "financial" in tags
        assert "banking" in tags

    def test_execute_replace_mode(self, tmp_path: Path) -> None:
        """Execute in replace mode removes existing tags."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        manager = TagManager()
        manager.write_tags(test_file, ["old_tag"])

        action = TagAction(fields=["domain"], mode=TagMode.REPLACE)
        result = self._make_result()

        plan = action.plan(test_file, result)
        action_result = action.execute(plan)

        assert action_result.success is True

        tags = manager.read_tags(test_file)
        assert tags == ["financial"]
        assert "old_tag" not in tags

    def test_default_fields(self) -> None:
        """Default fields are domain, category, doctype."""
        action = TagAction()

        assert action.fields == ["domain", "category", "doctype"]
        assert action.mode == TagMode.ADD
