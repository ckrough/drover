"""macOS filesystem tag operations and TagAction implementation."""

from __future__ import annotations

import contextlib
import plistlib
import sys
from enum import StrEnum
from typing import TYPE_CHECKING

from drover.actions.base import ActionPlan, ActionResult
from drover.logging import get_logger

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType

    from drover.models import ClassificationResult

logger = get_logger(__name__)

# macOS extended attribute for user tags
MACOS_TAG_ATTR = "com.apple.metadata:_kMDItemUserTags"


class TagMode(StrEnum):
    """Mode for applying tags to files."""

    REPLACE = "replace"  # Replace all existing tags
    ADD = "add"  # Add to existing tags (default)
    UPDATE = "update"  # Only update if file already has tags
    MISSING = "missing"  # Only add if file has no tags


class TagError(Exception):
    """Error during tag operations."""

    pass


class TagManager:
    """Manages macOS filesystem tags via extended attributes.

    Tags are stored in the com.apple.metadata:_kMDItemUserTags xattr
    as a binary plist. Each tag is stored as "TagName\\n0" where the
    suffix indicates the color index (0 = no color, 1-7 = colors).
    """

    _xattr: ModuleType  # xattr module, lazily imported on macOS only

    def __init__(self) -> None:
        """Initialize TagManager, checking platform compatibility."""
        if sys.platform != "darwin":
            raise TagError("macOS filesystem tags are only supported on macOS")

        # Import xattr lazily to avoid import errors on non-macOS
        try:
            import xattr

            self._xattr = xattr
        except ImportError as e:
            raise TagError("xattr library required: pip install xattr") from e

    def read_tags(self, path: Path) -> list[str]:
        """Read existing tags from a file.

        Args:
            path: Path to the file.

        Returns:
            List of tag names (without color suffixes).

        Raises:
            TagError: If reading tags fails due to permission or other errors.
        """
        try:
            data = self._xattr.getxattr(str(path), MACOS_TAG_ATTR)
            tags_with_colors = plistlib.loads(data)

            # Validate plist structure: must be list of strings
            if not isinstance(tags_with_colors, list):
                logger.warning(
                    "tag_read_invalid_format",
                    file=str(path),
                    error="Expected list, got " + type(tags_with_colors).__name__,
                )
                return []

            result = []
            for tag in tags_with_colors:
                if isinstance(tag, str):
                    # Strip the color suffix (e.g., "TagName\n0" -> "TagName")
                    result.append(tag.split("\n")[0])
                else:
                    logger.warning(
                        "tag_read_invalid_entry",
                        file=str(path),
                        error=f"Expected string, got {type(tag).__name__}",
                    )
            return result
        except OSError as e:
            # ENOATTR (93 on macOS) means no tags attribute exists - this is normal
            # Other OSErrors (permission denied, etc.) should be raised
            import errno

            if hasattr(e, "errno") and e.errno == errno.ENODATA:
                return []
            # On macOS, xattr raises OSError with errno 93 for missing attribute
            # which maps to ENOATTR, but Python uses ENODATA (61) or raw 93
            if hasattr(e, "errno") and e.errno == 93:
                return []
            raise TagError(f"Failed to read tags from {path}: {e}") from e
        except plistlib.InvalidFileException as e:
            logger.warning("tag_read_invalid_plist", file=str(path), error=str(e))
            return []
        except Exception as e:
            logger.warning("tag_read_failed", file=str(path), error=str(e))
            raise TagError(f"Failed to read tags from {path}: {e}") from e

    def write_tags(self, path: Path, tags: list[str]) -> None:
        """Write tags to a file, replacing all existing tags.

        Args:
            path: Path to the file.
            tags: List of tag names to write.

        Raises:
            TagError: If writing fails.
        """
        try:
            if not tags:
                with contextlib.suppress(OSError):
                    self._xattr.removexattr(str(path), MACOS_TAG_ATTR)
                return

            # Add color suffix (0 = no color) to each tag
            tags_with_colors = [f"{tag}\n0" for tag in tags]
            data = plistlib.dumps(tags_with_colors, fmt=plistlib.FMT_BINARY)
            self._xattr.setxattr(str(path), MACOS_TAG_ATTR, data)
        except PermissionError as e:
            raise TagError(f"Permission denied writing tags to {path}") from e
        except Exception as e:
            raise TagError(f"Failed to write tags to {path}: {e}") from e

    def add_tags(self, path: Path, tags: list[str]) -> None:
        """Add tags to a file, preserving existing tags.

        Note: This operation is not atomic. There is a potential race condition
        (TOCTOU) between reading and writing tags. If another process modifies
        tags between the read and write, those changes may be lost. For most
        use cases (single-user document organization), this is acceptable.

        Args:
            path: Path to the file.
            tags: List of tag names to add.
        """
        existing = self.read_tags(path)
        new_tags = existing + [t for t in tags if t not in existing]
        self.write_tags(path, new_tags)

    def remove_tags(self, path: Path, tags: list[str]) -> None:
        """Remove specific tags from a file.

        Note: This operation is not atomic. See add_tags() for details on
        the TOCTOU race condition.

        Args:
            path: Path to the file.
            tags: List of tag names to remove.
        """
        existing = self.read_tags(path)
        new_tags = [t for t in existing if t not in tags]
        self.write_tags(path, new_tags)

    def clear_tags(self, path: Path) -> None:
        """Remove all tags from a file.

        Args:
            path: Path to the file.
        """
        self.write_tags(path, [])


def tags_from_result(result: ClassificationResult, fields: list[str]) -> list[str]:
    """Extract tag values from a classification result.

    Args:
        result: Classification result.
        fields: List of field names to extract (e.g., ["domain", "category"]).

    Returns:
        List of tag values.
    """
    tags = []
    for field in fields:
        if field == "date":
            # Extract year from YYYYMMDD format
            if result.date and len(result.date) >= 4:
                tags.append(result.date[:4])
        else:
            value = getattr(result, field, None)
            if value:
                tags.append(value)
    return tags


def compute_final_tags(existing: list[str], new: list[str], mode: TagMode) -> list[str]:
    """Compute the final tag list based on mode.

    Args:
        existing: Existing tags on the file.
        new: New tags from classification.
        mode: How to combine existing and new tags.

    Returns:
        Final list of tags to apply.
    """
    match mode:
        case TagMode.REPLACE:
            return new
        case TagMode.ADD:
            return existing + [t for t in new if t not in existing]
        case TagMode.UPDATE:
            if existing:
                return new
            return existing  # No change if no tags exist
        case TagMode.MISSING:
            if not existing:
                return new
            return existing  # No change if tags already exist


class TagAction:
    """Action that applies macOS filesystem tags based on classification.

    Implements the FileAction protocol for use with ActionRunner.
    """

    def __init__(
        self,
        fields: list[str] | None = None,
        mode: TagMode = TagMode.ADD,
    ) -> None:
        """Initialize TagAction.

        Args:
            fields: Fields to extract for tags (default: domain, category, doctype).
            mode: How to apply tags relative to existing tags.
        """
        self.fields = fields or ["domain", "category", "doctype"]
        self.mode = mode
        self._manager: TagManager | None = None

    @property
    def manager(self) -> TagManager:
        """Lazy initialization of TagManager."""
        if self._manager is None:
            self._manager = TagManager()
        return self._manager

    def plan(self, file: Path, result: ClassificationResult) -> ActionPlan:
        """Plan tag changes for a file.

        Args:
            file: The file to tag.
            result: Classification result.

        Returns:
            ActionPlan with planned tag changes.

        Raises:
            FileNotFoundError: If the file does not exist.
        """
        if not file.exists():
            raise FileNotFoundError(f"File not found: {file}")

        existing = self.manager.read_tags(file)
        new_tags = tags_from_result(result, self.fields)
        final = compute_final_tags(existing, new_tags, self.mode)

        added = [t for t in final if t not in existing]
        removed = [t for t in existing if t not in final]

        if added or removed:
            parts = []
            if added:
                parts.append(f"add: {added}")
            if removed:
                parts.append(f"remove: {removed}")
            description = ", ".join(parts)
        else:
            description = "no changes"

        return ActionPlan(
            file=file,
            description=description,
            changes={
                "existing_tags": existing,
                "final_tags": final,
                "tags_added": added,
                "tags_removed": removed,
            },
        )

    def execute(self, plan: ActionPlan) -> ActionResult:
        """Execute the tag changes.

        Args:
            plan: The action plan to execute.

        Returns:
            ActionResult with the outcome.
        """
        try:
            final_tags = plan.changes.get("final_tags", [])
            self.manager.write_tags(plan.file, final_tags)

            return ActionResult(
                file=plan.file,
                success=True,
                description=plan.description,
                changes={
                    "tags_added": plan.changes.get("tags_added", []),
                    "tags_removed": plan.changes.get("tags_removed", []),
                },
            )
        except TagError as e:
            return ActionResult(
                file=plan.file,
                success=False,
                description="Failed to apply tags",
                error=str(e),
            )
        except Exception as e:
            return ActionResult(
                file=plan.file,
                success=False,
                description="Unexpected error",
                error=str(e),
            )
