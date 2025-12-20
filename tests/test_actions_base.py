"""Tests for the action infrastructure."""

from pathlib import Path

import pytest

from drover.actions.base import ActionPlan, ActionResult
from drover.actions.runner import ActionRunner
from drover.config import DroverConfig, ErrorMode
from drover.models import ClassificationResult


class MockAction:
    """Mock action for testing."""

    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.planned: list[tuple[Path, ClassificationResult]] = []
        self.executed: list[ActionPlan] = []

    def plan(self, file: Path, result: ClassificationResult) -> ActionPlan:
        self.planned.append((file, result))
        return ActionPlan(
            file=file,
            description=f"Mock action for {file.name}",
            changes={"mock_field": result.domain},
        )

    def execute(self, plan: ActionPlan) -> ActionResult:
        self.executed.append(plan)
        if self.should_fail:
            return ActionResult(
                file=plan.file,
                success=False,
                description="Mock failure",
                error="Simulated error",
            )
        return ActionResult(
            file=plan.file,
            success=True,
            description=plan.description,
            changes=plan.changes,
        )


def _make_fake_classify(tmp_path: Path):
    """Create a fake classify method for testing."""

    async def fake_classify(
        content: str, capture_debug: bool = False, collect_metrics: bool = False
    ):
        return (
            ClassificationResult(
                original="test.txt",
                suggested_path="financial/banking/statement/test.txt",
                suggested_filename="statement-vendor-subject-20250101.txt",
                domain="financial",
                category="banking",
                doctype="statement",
                vendor="vendor",
                date="20250101",
                subject="subject",
            ),
            None,
        )

    return fake_classify


class TestActionPlan:
    """Tests for ActionPlan dataclass."""

    def test_to_dict(self) -> None:
        """ActionPlan.to_dict returns expected structure."""
        plan = ActionPlan(
            file=Path("/test/file.pdf"),
            description="Add tags",
            changes={"tags_added": ["financial", "banking"]},
        )

        result = plan.to_dict()

        assert result["file"] == "/test/file.pdf"
        assert result["description"] == "Add tags"
        assert result["dry_run"] is True
        assert result["tags_added"] == ["financial", "banking"]


class TestActionResult:
    """Tests for ActionResult dataclass."""

    def test_to_dict_success(self) -> None:
        """ActionResult.to_dict for successful result."""
        result = ActionResult(
            file=Path("/test/file.pdf"),
            success=True,
            description="Tags applied",
            changes={"tags_added": ["financial"]},
        )

        output = result.to_dict()

        assert output["file"] == "/test/file.pdf"
        assert output["success"] is True
        assert output["tags_added"] == ["financial"]
        assert "error" not in output

    def test_to_dict_failure(self) -> None:
        """ActionResult.to_dict for failed result includes error."""
        result = ActionResult(
            file=Path("/test/file.pdf"),
            success=False,
            description="Failed",
            error="Permission denied",
        )

        output = result.to_dict()

        assert output["success"] is False
        assert output["error"] == "Permission denied"


class TestActionRunner:
    """Tests for ActionRunner orchestration."""

    @pytest.mark.asyncio
    async def test_empty_files_returns_zero(self) -> None:
        """Empty file list returns exit code 0."""
        config = DroverConfig()
        action = MockAction()
        runner = ActionRunner(config, action)

        exit_code = await runner.run([])

        assert exit_code == 0
        assert len(action.planned) == 0
        assert len(action.executed) == 0

    @pytest.mark.asyncio
    async def test_dry_run_plans_without_executing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Dry run generates plans but doesn't execute."""
        doc_path = tmp_path / "test.txt"
        doc_path.write_text("test content")

        config = DroverConfig()
        action = MockAction()
        runner = ActionRunner(config, action)

        monkeypatch.setattr(runner._service._classifier, "classify", _make_fake_classify(tmp_path))

        outputs: list[ActionPlan | ActionResult] = []

        def collect(output: ActionPlan | ActionResult) -> None:
            outputs.append(output)

        exit_code = await runner.run([doc_path], dry_run=True, on_result=collect)

        assert exit_code == 0
        assert len(action.planned) == 1
        assert len(action.executed) == 0
        assert len(outputs) == 1
        assert isinstance(outputs[0], ActionPlan)

    @pytest.mark.asyncio
    async def test_execute_mode_runs_action(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Execute mode plans and executes."""
        doc_path = tmp_path / "test.txt"
        doc_path.write_text("test content")

        config = DroverConfig()
        action = MockAction()
        runner = ActionRunner(config, action)

        monkeypatch.setattr(runner._service._classifier, "classify", _make_fake_classify(tmp_path))

        outputs: list[ActionPlan | ActionResult] = []

        def collect(output: ActionPlan | ActionResult) -> None:
            outputs.append(output)

        exit_code = await runner.run([doc_path], dry_run=False, on_result=collect)

        assert exit_code == 0
        assert len(action.planned) == 1
        assert len(action.executed) == 1
        assert len(outputs) == 1
        assert isinstance(outputs[0], ActionResult)
        assert outputs[0].success is True

    @pytest.mark.asyncio
    async def test_action_failure_returns_partial_exit_code(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Action failure returns exit code 1 for partial failure."""
        doc_path = tmp_path / "test.txt"
        doc_path.write_text("test content")

        config = DroverConfig()
        action = MockAction(should_fail=True)
        runner = ActionRunner(config, action)

        monkeypatch.setattr(runner._service._classifier, "classify", _make_fake_classify(tmp_path))

        exit_code = await runner.run([doc_path], dry_run=False)

        # With one file that failed action, should be exit code 2 (all failed)
        assert exit_code == 2

    @pytest.mark.asyncio
    async def test_classification_error_skips_action(self, tmp_path: Path) -> None:
        """Classification errors don't trigger action planning."""
        missing_file = tmp_path / "missing.pdf"

        config = DroverConfig(on_error=ErrorMode.CONTINUE)
        action = MockAction()
        runner = ActionRunner(config, action)

        exit_code = await runner.run([missing_file], dry_run=False)

        assert exit_code == 2  # All files failed classification
        assert len(action.planned) == 0
        assert len(action.executed) == 0
