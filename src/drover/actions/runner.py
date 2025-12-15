"""Action runner that orchestrates classification and action execution."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from drover.actions.base import ActionPlan, ActionResult, FileAction
from drover.config import DroverConfig
from drover.logging import get_logger
from drover.models import ClassificationErrorResult, ClassificationResult
from drover.service import ClassificationService

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

ActionOutput = ActionPlan | ActionResult
ActionCallback = Callable[[ActionOutput], None]


class ActionRunner:
    """Orchestrates classification and action execution.

    This class wraps ClassificationService and applies a FileAction to each
    successfully classified file. It supports dry-run mode where only plans
    are generated without execution.
    """

    def __init__(self, config: DroverConfig, action: FileAction) -> None:
        """Initialize the action runner.

        Args:
            config: Drover configuration.
            action: The action to apply to classified files.
        """
        self.config = config
        self.action = action
        self._service = ClassificationService(config)
        # Map full file path (Path) -> classification result
        # Uses Path objects to handle duplicate filenames in different directories
        self._file_results: dict[Path, ClassificationResult] = {}

    async def run(
        self,
        files: Sequence[Path],
        dry_run: bool = False,
        on_result: ActionCallback | None = None,
    ) -> int:
        """Classify files and apply action to each.

        Args:
            files: Files to process.
            dry_run: If True, only generate plans without executing.
            on_result: Optional callback for each action output.

        Returns:
            Exit code (0=success, 1=partial failure, 2=complete failure).
        """
        if not files:
            return 0

        action_errors = 0
        classification_errors = 0

        # Build reverse mapping: filename -> Path
        # For duplicate filenames, we track the full path for each file
        # and match results by filename (result.original) to their Path
        filename_to_paths: dict[str, list[Path]] = {}
        for f in files:
            filename_to_paths.setdefault(f.name, []).append(f)

        # Track which paths we've matched for each filename
        matched_indices: dict[str, int] = {}

        def handle_classification(
            result: ClassificationResult | ClassificationErrorResult,
        ) -> None:
            nonlocal action_errors, classification_errors

            # Handle classification errors - report to callback as ActionResult
            if isinstance(result, ClassificationErrorResult) or result.error:
                classification_errors += 1
                error_msg = getattr(result, "error_message", None) or getattr(
                    result, "error", "Unknown error"
                )
                logger.warning(
                    "classification_failed",
                    file=result.original,
                    error=error_msg,
                )

                # Find the matching Path and report error to callback
                filename = result.original
                paths = filename_to_paths.get(filename, [])
                idx = matched_indices.get(filename, 0)
                if paths and idx < len(paths):
                    file_path = paths[idx]
                    matched_indices[filename] = idx + 1
                    if on_result is not None:
                        on_result(
                            ActionResult(
                                file=file_path,
                                success=False,
                                description="Classification failed",
                                error=str(error_msg),
                            )
                        )
                return

            # Find the matching Path for this result
            # Results come back with filename only (result.original), so we need to
            # match them back to full paths. For duplicate filenames, we match in order.
            filename = result.original
            paths = filename_to_paths.get(filename, [])
            if not paths:
                logger.warning(
                    "classification_result_unmatched",
                    file=filename,
                )
                return

            idx = matched_indices.get(filename, 0)
            if idx < len(paths):
                file_path = paths[idx]
                matched_indices[filename] = idx + 1
                self._file_results[file_path] = result
            else:
                logger.warning(
                    "classification_result_extra",
                    file=filename,
                    expected_count=len(paths),
                )

        # Run classification
        exit_code = await self._service.classify_files(
            list(files),
            on_result=handle_classification,
        )

        # If all classifications failed, return early
        if exit_code == 2:
            return 2

        # Apply actions to successfully classified files
        for file_path in files:
            if file_path not in self._file_results:
                continue

            result = self._file_results[file_path]

            try:
                plan = self.action.plan(file_path, result)

                if dry_run:
                    logger.debug(
                        "action_planned",
                        file=str(file_path),
                        description=plan.description,
                    )
                    if on_result is not None:
                        on_result(plan)
                else:
                    action_result = self.action.execute(plan)
                    if not action_result.success:
                        action_errors += 1
                        logger.warning(
                            "action_failed",
                            file=str(file_path),
                            error=action_result.error,
                        )
                    else:
                        logger.debug(
                            "action_executed",
                            file=str(file_path),
                            description=action_result.description,
                        )
                    if on_result is not None:
                        on_result(action_result)

            except Exception as e:
                action_errors += 1
                logger.exception(
                    "action_error",
                    file=str(file_path),
                    error=str(e),
                )
                if on_result is not None:
                    on_result(
                        ActionResult(
                            file=file_path,
                            success=False,
                            description="Action failed",
                            error=str(e),
                        )
                    )

        # Determine exit code
        total_files = len(files)
        total_errors = classification_errors + action_errors
        successful = total_files - total_errors

        if successful == 0:
            return 2
        if total_errors > 0:
            return 1
        return 0
