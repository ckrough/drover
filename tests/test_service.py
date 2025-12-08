"""Tests for the ClassificationService orchestration layer."""

from pathlib import Path

import pytest

from drover.config import DroverConfig, ErrorMode
from drover.models import ClassificationErrorResult, ClassificationResult
from drover.service import ClassificationService


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

    async def fake_classify(content: str, capture_debug: bool = False, collect_metrics: bool = False):  # type: ignore[override]
        debug_info = {"prompt": "PROMPT", "response": "RESPONSE"} if capture_debug else None
        return (
            ClassificationResult(
                original="doc.txt",
                suggested_path=str(doc_path),
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
