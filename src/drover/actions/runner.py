"""Action runner that orchestrates classification and action execution."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from drover.actions.base import ActionPlan, ActionResult, FileAction
from drover.logging import get_logger
from drover.models import ClassificationErrorResult, ClassificationResult
from drover.service import ClassificationService, make_filename_matcher

if TYPE_CHECKING:
    from drover.config import DroverConfig

logger = get_logger(__name__)

ActionOutput = ActionPlan | ActionResult
ActionCallback = Callable[[ActionOutput], None]


class ActionRunner:
    """Orchestrates classification and action execution.

    Wraps ClassificationService and applies an ordered chain of
    FileActions to each successfully classified file. Each action
    receives the file path produced by the previous action (via the
    ``final_path`` entry in changes); when an action signals
    ``halt_chain=True`` the chain stops for that file.
    """

    def __init__(self, config: DroverConfig, actions: Sequence[FileAction]) -> None:
        """Initialize the action runner.

        Args:
            config: Drover configuration.
            actions: Ordered list of actions to apply per file. The first
                action receives the original source path; subsequent
                actions receive the ``final_path`` from the previous
                action's plan or result.
        """
        self.config = config
        self.actions: list[FileAction] = list(actions)
        self._service = ClassificationService(config)
        self._file_results: dict[Path, ClassificationResult] = {}

    async def run(
        self,
        files: Sequence[Path],
        dry_run: bool = False,
        on_result: ActionCallback | None = None,
    ) -> int:
        """Classify files and apply the action chain to each.

        Args:
            files: Files to process.
            dry_run: If True, only generate plans without executing.
            on_result: Optional callback invoked once per emitted plan or
                result. Each chained action emits a separate event.

        Returns:
            Exit code (0=success, 1=partial failure, 2=complete failure).
        """
        if not files:
            return 0

        action_errors = 0
        classification_errors = 0
        match_path = make_filename_matcher(files)

        def handle_classification(
            result: ClassificationResult | ClassificationErrorResult,
        ) -> None:
            nonlocal classification_errors

            file_path = match_path(result.original)

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
                if file_path is not None and on_result is not None:
                    on_result(
                        ActionResult(
                            file=file_path,
                            success=False,
                            description="Classification failed",
                            error=str(error_msg),
                        )
                    )
                return

            if file_path is None:
                logger.warning(
                    "classification_result_unmatched",
                    file=result.original,
                )
                return

            self._file_results[file_path] = result

        exit_code = await self._service.classify_files(
            list(files),
            on_result=handle_classification,
        )

        if exit_code == 2:
            return 2

        for file_path in files:
            if file_path not in self._file_results:
                continue

            result = self._file_results[file_path]
            chain_failed = self._run_chain(file_path, result, dry_run, on_result)
            if chain_failed:
                action_errors += 1

        total_files = len(files)
        total_errors = classification_errors + action_errors
        successful = total_files - total_errors

        if successful == 0:
            return 2
        if total_errors > 0:
            return 1
        return 0

    def _run_chain(
        self,
        file_path: Path,
        result: ClassificationResult,
        dry_run: bool,
        on_result: ActionCallback | None,
    ) -> bool:
        """Run the action chain for one file. Returns True on action error."""
        current_path = file_path

        for action in self.actions:
            try:
                plan = action.plan(current_path, result)
            except Exception as exc:
                logger.exception(
                    "action_plan_error",
                    file=str(current_path),
                    error=str(exc),
                )
                if on_result is not None:
                    on_result(
                        ActionResult(
                            file=current_path,
                            success=False,
                            description="Action plan failed",
                            error=str(exc),
                        )
                    )
                return True

            if dry_run:
                logger.debug(
                    "action_planned",
                    file=str(current_path),
                    description=plan.description,
                )
                if on_result is not None:
                    on_result(plan)
                next_path = plan.changes.get("final_path")
                if isinstance(next_path, Path):
                    current_path = next_path
                if plan.changes.get("halt_chain", False):
                    return False
                continue

            try:
                action_result = action.execute(plan)
            except Exception as exc:
                logger.exception(
                    "action_error",
                    file=str(current_path),
                    error=str(exc),
                )
                if on_result is not None:
                    on_result(
                        ActionResult(
                            file=current_path,
                            success=False,
                            description="Action failed",
                            error=str(exc),
                        )
                    )
                return True

            if not action_result.success:
                logger.warning(
                    "action_failed",
                    file=str(current_path),
                    error=action_result.error,
                )
                if on_result is not None:
                    on_result(action_result)
                return True

            logger.debug(
                "action_executed",
                file=str(current_path),
                description=action_result.description,
            )
            if on_result is not None:
                on_result(action_result)

            next_path = action_result.changes.get("final_path")
            if isinstance(next_path, Path):
                current_path = next_path
            if action_result.changes.get("halt_chain", False):
                return False

        return False
