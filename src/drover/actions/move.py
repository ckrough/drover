"""File move/copy action for the organize pipeline."""

from __future__ import annotations

import contextlib
import shutil
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING

from drover.actions.base import ActionPlan, ActionResult
from drover.logging import get_logger

if TYPE_CHECKING:
    from drover.models import ClassificationResult

logger = get_logger(__name__)


class MoveStatus(StrEnum):
    """Status values produced by MoveAction.plan and MoveAction.execute."""

    MOVED = "moved"
    COPIED = "copied"
    SKIPPED_EXISTS = "skipped_exists"
    ERROR = "error"
    WOULD_MOVE = "would_move"
    WOULD_COPY = "would_copy"
    WOULD_SKIP_EXISTS = "would_skip_exists"


class MoveAction:
    """Move (or copy) a classified file into a destination tree.

    Implements the FileAction protocol. The destination is computed as
    `{dest_root}/{ClassificationResult.suggested_path}`. If the destination
    exists, the file is left in place and the result reports
    `skipped_exists`. Same-volume moves use os.rename; cross-volume moves
    fall back to copy + remove. The source is removed only after the
    destination write succeeds; any error leaves the source intact.
    """

    def __init__(self, dest_root: Path, copy: bool = False) -> None:
        """Initialize MoveAction.

        Args:
            dest_root: Root directory under which classified paths are written.
            copy: If True, the source file is left in place and the
                destination is a copy. Defaults to False (move semantics).
        """
        self.dest_root = Path(dest_root).expanduser().resolve()
        self.copy = copy

    def plan(self, file: Path, result: ClassificationResult) -> ActionPlan:
        """Compute the destination for the file and detect collisions."""
        destination = self.dest_root / result.suggested_path
        exists = destination.exists()

        if exists:
            description = f"would skip (destination exists): {destination}"
            status = MoveStatus.WOULD_SKIP_EXISTS
            final_path: Path = file
            halt_chain = True
        else:
            verb = "copy" if self.copy else "move"
            description = f"would {verb} to {destination}"
            status = MoveStatus.WOULD_COPY if self.copy else MoveStatus.WOULD_MOVE
            final_path = destination
            halt_chain = False

        return ActionPlan(
            file=file,
            description=description,
            changes={
                "destination": str(destination),
                "status": status.value,
                "copy": self.copy,
                "would_skip_exists": exists,
                "final_path": final_path,
                "halt_chain": halt_chain,
            },
        )

    def execute(self, plan: ActionPlan) -> ActionResult:
        """Apply the planned move (or copy)."""
        source = plan.file
        destination = Path(plan.changes["destination"])
        copy_mode = bool(plan.changes.get("copy", False))
        skip_exists = bool(plan.changes.get("would_skip_exists", False))

        if skip_exists:
            return ActionResult(
                file=source,
                success=True,
                description=f"skipped (destination exists): {destination}",
                changes={
                    "destination": str(destination),
                    "status": MoveStatus.SKIPPED_EXISTS.value,
                    "final_path": source,
                    "halt_chain": True,
                },
            )

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return self._error_result(source, destination, copy_mode, str(exc))

        if copy_mode:
            try:
                shutil.copy2(str(source), str(destination))
            except Exception as exc:
                return self._error_result(source, destination, copy_mode, str(exc))
            return ActionResult(
                file=source,
                success=True,
                description=f"copied to {destination}",
                changes={
                    "destination": str(destination),
                    "status": MoveStatus.COPIED.value,
                    "final_path": destination,
                    "halt_chain": False,
                },
            )

        try:
            source.rename(destination)
        except OSError:
            partial = self._cross_volume_move(source, destination)
            if partial is not None:
                return partial
        except Exception as exc:
            return self._error_result(source, destination, copy_mode, str(exc))

        return ActionResult(
            file=source,
            success=True,
            description=f"moved to {destination}",
            changes={
                "destination": str(destination),
                "status": MoveStatus.MOVED.value,
                "final_path": destination,
                "halt_chain": False,
            },
        )

    def _cross_volume_move(
        self, source: Path, destination: Path
    ) -> ActionResult | None:
        """Handle cross-volume move via copy + remove.

        Returns an ActionResult only on partial failure (copy succeeded
        but source removal failed). Returns None on full success so the
        caller can build the standard MOVED result.
        """
        try:
            shutil.copy2(str(source), str(destination))
        except Exception as exc:
            if destination.exists():
                with contextlib.suppress(OSError):
                    destination.unlink()
            return self._error_result(source, destination, False, str(exc))

        try:
            source.unlink()
        except OSError as exc:
            return ActionResult(
                file=source,
                success=False,
                description=f"partial move to {destination}: source removal failed",
                error=(
                    f"copy succeeded to {destination} but failed to remove "
                    f"source {source}: {exc}"
                ),
                changes={
                    "destination": str(destination),
                    "status": MoveStatus.ERROR.value,
                    "final_path": destination,
                    "halt_chain": True,
                    "partial": True,
                },
            )
        return None

    @staticmethod
    def _error_result(
        source: Path, destination: Path, copy_mode: bool, error: str
    ) -> ActionResult:
        verb = "copy" if copy_mode else "move"
        return ActionResult(
            file=source,
            success=False,
            description=f"failed to {verb} to {destination}",
            error=error,
            changes={
                "destination": str(destination),
                "status": MoveStatus.ERROR.value,
                "final_path": source,
                "halt_chain": True,
            },
        )
