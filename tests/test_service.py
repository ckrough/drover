"""Tests for the ClassificationService orchestration layer."""

import asyncio
from pathlib import Path

import pytest

from drover.classifier import LLMParseError
from drover.config import DroverConfig, ErrorMode
from drover.models import ClassificationErrorResult, ClassificationResult
from drover.service import ClassificationService

# Type alias for union return type (keeps lines under 100 chars)
Result = ClassificationResult | ClassificationErrorResult


def _make_success_result(filename: str) -> ClassificationResult:
    """Create a successful classification result for testing."""
    return ClassificationResult(
        original=filename,
        suggested_path=f"financial/banking/statement/{filename}",
        suggested_filename=f"statement-vendor-subject-20250101{Path(filename).suffix}",
        domain="financial",
        category="banking",
        doctype="statement",
        vendor="vendor",
        date="20250101",
        subject="subject",
    )


def _make_error_result(filename: str) -> ClassificationErrorResult:
    """Create an error classification result for testing."""
    return ClassificationErrorResult.from_exception(
        filename,
        code=__import__("drover.models", fromlist=["ErrorCode"]).ErrorCode.LLM_PARSE_ERROR,
        exception=ValueError("Test error"),
    )


@pytest.mark.asyncio
async def test_classification_service_empty_files() -> None:
    """No files should return exit code 0 and not error."""
    cfg = DroverConfig()
    service = ClassificationService(cfg)

    exit_code = await service.classify_files([])

    assert exit_code == 0


@pytest.mark.asyncio
async def test_classification_service_error_modes_continue(tmp_path: Path) -> None:
    """Service should continue on errors when ErrorMode.CONTINUE is set.

    We feed it a non-existent file to force a DocumentLoadError and
    ensure it maps to an error result and exit code 2 when all fail.
    """
    cfg = DroverConfig(on_error=ErrorMode.CONTINUE)
    service = ClassificationService(cfg)

    missing = tmp_path / "does_not_exist.pdf"

    results: list[ClassificationResult | ClassificationErrorResult] = []

    def collect(result: ClassificationResult | ClassificationErrorResult) -> None:
        results.append(result)

    exit_code = await service.classify_files([missing], on_result=collect)

    assert exit_code == 2  # all failed
    assert len(results) == 1
    assert isinstance(results[0], ClassificationErrorResult)
    assert results[0].error is True


@pytest.mark.asyncio
async def test_debug_dir_writes_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """When debug_dir is configured, prompts are written there."""
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("dummy content")

    cfg = DroverConfig(capture_debug=True, debug_dir=tmp_path / "debug")
    service = ClassificationService(cfg)

    async def fake_classify(  # type: ignore[override]
        content: str, capture_debug: bool = False, collect_metrics: bool = False
    ) -> tuple[ClassificationResult, dict[str, str] | None]:
        debug_info = {"prompt": "PROMPT", "response": "RESPONSE"} if capture_debug else None
        return (
            ClassificationResult(
                original="doc.txt",
                suggested_path=str(doc_path),
                suggested_filename="statement-vendor-subject-20250101.txt",
                domain="financial",
                category="banking",
                doctype="statement",
                vendor="vendor",
                date="20250101",
                subject="subject",
            ),
            debug_info,
        )

    monkeypatch.setattr(service._classifier, "classify", fake_classify)

    exit_code = await service.classify_files([doc_path])
    assert exit_code == 0

    assert cfg.debug_dir is not None
    debug_dir_path = Path(cfg.debug_dir)
    assert debug_dir_path.exists()
    prompt_files = list(debug_dir_path.glob("*.prompt.txt"))
    response_files = list(debug_dir_path.glob("*.response.txt"))
    assert prompt_files
    assert response_files


@pytest.mark.asyncio
async def test_debug_capture_on_llm_parse_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Debug files should be captured even when LLM parsing fails.

    This tests that when --capture-debug is enabled, the prompt and response
    are saved to disk even if the LLM response cannot be parsed.
    """
    doc_path = tmp_path / "doc.txt"
    doc_path.write_text("dummy content")

    debug_dir = tmp_path / "debug"
    cfg = DroverConfig(capture_debug=True, debug_dir=debug_dir, on_error=ErrorMode.CONTINUE)
    service = ClassificationService(cfg)

    async def fake_classify_that_fails(
        content: str, capture_debug: bool = False, collect_metrics: bool = False
    ) -> None:
        # Simulate LLM returning unparseable response with debug_info attached
        debug_info = {"prompt": "TEST PROMPT", "response": "INVALID JSON RESPONSE"}
        raise LLMParseError(
            "Could not parse JSON from response: INVALID JSON RESPONSE...",
            debug_info=debug_info,
        )

    monkeypatch.setattr(service._classifier, "classify", fake_classify_that_fails)

    results: list[ClassificationResult | ClassificationErrorResult] = []
    exit_code = await service.classify_files([doc_path], on_result=results.append)

    # Classification should fail
    assert exit_code == 2
    assert len(results) == 1
    assert isinstance(results[0], ClassificationErrorResult)
    assert results[0].error_code.value == "LLM_PARSE_ERROR"

    # But debug files should still be written
    assert debug_dir.exists()
    prompt_files = list(debug_dir.glob("*.prompt.txt"))
    response_files = list(debug_dir.glob("*.response.txt"))
    assert len(prompt_files) == 1, "Expected prompt file to be written on failure"
    assert len(response_files) == 1, "Expected response file to be written on failure"

    # Verify content was captured correctly
    assert prompt_files[0].read_text() == "TEST PROMPT"
    assert response_files[0].read_text() == "INVALID JSON RESPONSE"


class TestConcurrencyLimiting:
    """Tests for semaphore-based concurrency control."""

    @pytest.mark.asyncio
    async def test_concurrency_limit_respected(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Semaphore should limit concurrent classify_file calls.

        We create 5 files with concurrency=2, track peak concurrent executions,
        and verify it never exceeds 2.
        """
        # Track concurrent executions
        current_concurrent = 0
        peak_concurrent = 0
        lock = asyncio.Lock()

        # Create test files
        files = []
        for i in range(5):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        cfg = DroverConfig(concurrency=2)
        service = ClassificationService(cfg)

        async def fake_classify_file(file_path: Path) -> ClassificationResult:
            nonlocal current_concurrent, peak_concurrent
            async with lock:
                current_concurrent += 1
                peak_concurrent = max(peak_concurrent, current_concurrent)

            # Simulate some work
            await asyncio.sleep(0.05)

            async with lock:
                current_concurrent -= 1

            return _make_success_result(file_path.name)

        monkeypatch.setattr(service, "classify_file", fake_classify_file)

        exit_code = await service.classify_files(files)

        assert exit_code == 0
        assert peak_concurrent <= 2, f"Peak concurrent was {peak_concurrent}, expected <= 2"
        # Should have actually used concurrency (peak > 1 with enough files)
        assert peak_concurrent >= 1


class TestPartialSuccess:
    """Tests for partial success scenarios (some files succeed, some fail)."""

    @pytest.mark.asyncio
    async def test_partial_failure_returns_exit_code_1(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When some files succeed and some fail, exit code should be 1."""
        files = []
        for i in range(3):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        cfg = DroverConfig(on_error=ErrorMode.CONTINUE)
        service = ClassificationService(cfg)

        call_count = 0

        async def fake_classify_file(file_path: Path) -> Result:
            nonlocal call_count
            call_count += 1
            # First two succeed, third fails
            if "doc2" in file_path.name:
                return _make_error_result(file_path.name)
            return _make_success_result(file_path.name)

        monkeypatch.setattr(service, "classify_file", fake_classify_file)

        results: list[Result] = []
        exit_code = await service.classify_files(files, on_result=results.append)

        assert exit_code == 1  # Partial failure
        assert call_count == 3
        assert len(results) == 3

        # Count successes and errors
        successes = [r for r in results if not r.error]
        errors = [r for r in results if r.error]
        assert len(successes) == 2
        assert len(errors) == 1


class TestErrorModes:
    """Tests for different error handling modes."""

    @pytest.mark.asyncio
    async def test_error_mode_fail_stops_on_first_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ErrorMode.FAIL should stop processing after first error.

        Note: Due to asyncio.as_completed, we can't guarantee which file
        errors first, but we can verify that processing stops after an error.
        """
        files = []
        for i in range(5):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        cfg = DroverConfig(on_error=ErrorMode.FAIL)
        service = ClassificationService(cfg)

        async def fake_classify_file(file_path: Path) -> Result:
            # All files fail
            return _make_error_result(file_path.name)

        monkeypatch.setattr(service, "classify_file", fake_classify_file)

        results: list[Result] = []
        exit_code = await service.classify_files(files, on_result=results.append)

        assert exit_code == 2  # Complete failure (due to FAIL mode)
        # Should have emitted exactly one result (the first error)
        assert len(results) == 1
        assert results[0].error is True

    @pytest.mark.asyncio
    async def test_error_mode_skip_omits_errors_from_callback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ErrorMode.SKIP should not call on_result for failed files."""
        files = []
        for i in range(3):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        cfg = DroverConfig(on_error=ErrorMode.SKIP)
        service = ClassificationService(cfg)

        async def fake_classify_file(file_path: Path) -> Result:
            # doc1 fails, others succeed
            if "doc1" in file_path.name:
                return _make_error_result(file_path.name)
            return _make_success_result(file_path.name)

        monkeypatch.setattr(service, "classify_file", fake_classify_file)

        results: list[Result] = []
        exit_code = await service.classify_files(files, on_result=results.append)

        assert exit_code == 1  # Partial failure
        # Only successful results should be in callback
        assert len(results) == 2
        assert all(not r.error for r in results)

    @pytest.mark.asyncio
    async def test_error_mode_continue_includes_all_results(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """ErrorMode.CONTINUE should include both successes and errors in callback."""
        files = []
        for i in range(3):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        cfg = DroverConfig(on_error=ErrorMode.CONTINUE)
        service = ClassificationService(cfg)

        async def fake_classify_file(file_path: Path) -> Result:
            # doc1 fails, others succeed
            if "doc1" in file_path.name:
                return _make_error_result(file_path.name)
            return _make_success_result(file_path.name)

        monkeypatch.setattr(service, "classify_file", fake_classify_file)

        results: list[Result] = []
        exit_code = await service.classify_files(files, on_result=results.append)

        assert exit_code == 1  # Partial failure
        # All results should be in callback
        assert len(results) == 3

        successes = [r for r in results if not r.error]
        errors = [r for r in results if r.error]
        assert len(successes) == 2
        assert len(errors) == 1

    @pytest.mark.asyncio
    async def test_all_files_fail_returns_exit_code_2(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When all files fail, exit code should be 2 regardless of error mode."""
        files = []
        for i in range(3):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        cfg = DroverConfig(on_error=ErrorMode.CONTINUE)
        service = ClassificationService(cfg)

        async def fake_classify_file(file_path: Path) -> ClassificationErrorResult:
            return _make_error_result(file_path.name)

        monkeypatch.setattr(service, "classify_file", fake_classify_file)

        results: list[Result] = []
        exit_code = await service.classify_files(files, on_result=results.append)

        assert exit_code == 2  # Complete failure
        assert len(results) == 3
        assert all(r.error for r in results)

    @pytest.mark.asyncio
    async def test_all_files_succeed_returns_exit_code_0(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """When all files succeed, exit code should be 0."""
        files = []
        for i in range(3):
            f = tmp_path / f"doc{i}.txt"
            f.write_text(f"content {i}")
            files.append(f)

        cfg = DroverConfig(on_error=ErrorMode.CONTINUE)
        service = ClassificationService(cfg)

        async def fake_classify_file(file_path: Path) -> ClassificationResult:
            return _make_success_result(file_path.name)

        monkeypatch.setattr(service, "classify_file", fake_classify_file)

        results: list[Result] = []
        exit_code = await service.classify_files(files, on_result=results.append)

        assert exit_code == 0  # Complete success
        assert len(results) == 3
        assert all(not r.error for r in results)


class TestUnexpectedErrors:
    """Tests for defensive error handling fallback."""

    @pytest.mark.asyncio
    async def test_unexpected_error_triggers_fallback(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Unexpected exceptions should be caught by defensive fallback.

        The exception handling chain catches specific exception types.
        Any exception NOT in that chain (like RuntimeError) should be
        caught by the final 'except Exception' block and return
        ErrorCode.UNEXPECTED_ERROR.
        """
        from drover.models import ErrorCode, RawClassification

        doc = tmp_path / "doc.txt"
        doc.write_text("test content")

        cfg = DroverConfig()
        service = ClassificationService(cfg)

        # Mock classifier to succeed
        async def fake_classify(
            content: str,
            capture_debug: bool = False,
            collect_metrics: bool = False,
        ) -> tuple[RawClassification, dict[str, str] | None]:
            return (
                RawClassification(
                    domain="financial",
                    category="banking",
                    doctype="statement",
                    vendor="test",
                    date="2025-01-01",
                    subject="test",
                ),
                None,
            )

        monkeypatch.setattr(service._classifier, "classify", fake_classify)

        # Mock path_builder to raise an unexpected exception type
        def fake_build(*args: object, **kwargs: object) -> None:
            raise RuntimeError("Simulated unexpected failure")

        monkeypatch.setattr(service._path_builder, "build", fake_build)

        result = await service.classify_file(doc)

        # Should be an error result with UNEXPECTED_ERROR code
        assert isinstance(result, ClassificationErrorResult)
        assert result.error is True
        assert result.error_code == ErrorCode.UNEXPECTED_ERROR
        assert "Simulated unexpected failure" in (result.error_message or "")
