"""Base abstractions for file actions based on classification results."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from drover.models import ClassificationResult


@dataclass
class ActionPlan:
    """What an action intends to do.

    Used for dry-run output and as input to execute().
    """

    file: Path
    description: str
    changes: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        return {
            "file": str(self.file),
            "description": self.description,
            "dry_run": True,
            **self.changes,
        }


@dataclass
class ActionResult:
    """Outcome of an executed action."""

    file: Path
    success: bool
    description: str
    changes: dict[str, Any] = field(default_factory=dict)
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON output."""
        result: dict[str, Any] = {
            "file": str(self.file),
            "success": self.success,
            **self.changes,
        }
        if self.error:
            result["error"] = self.error
        return result


class FileAction(Protocol):
    """Protocol for file actions based on classification.

    Implementations must provide:
    - plan(): Determine what changes will be made (for dry-run)
    - execute(): Apply the planned changes
    """

    def plan(self, file: Path, result: ClassificationResult) -> ActionPlan:
        """Plan what this action will do.

        Args:
            file: The file to act on.
            result: Classification result for the file.

        Returns:
            ActionPlan describing the intended changes.
        """
        ...

    def execute(self, plan: ActionPlan) -> ActionResult:
        """Execute the planned action.

        Args:
            plan: The action plan to execute.

        Returns:
            ActionResult with the outcome.
        """
        ...
