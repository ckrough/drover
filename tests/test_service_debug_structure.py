"""Tests for --debug-structure dumps (prof-rbz).

The debug structure dump is now handled inside DoclingLoader.dump_structure(),
called during load() when debug_structure=True. These tests verify the dump
is written correctly and that the flag is respected.
"""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from drover.config import DroverConfig, LoaderType
from drover.loader import DoclingLoader, LoadedDocument


def _patch_classifier(service: object, monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the classifier with a no-op fake so tests stay LLM-free."""
    from drover.service import ClassificationService

    assert isinstance(service, ClassificationService)

    async def fake_classify(
        content: str,
        capture_debug: bool = False,
        collect_metrics: bool = False,
    ) -> object:
        from drover.models import RawClassification

        return (
            RawClassification(
                domain="financial",
                category="banking",
                doctype="statement",
                vendor="X",
                date="20250101",
                subject="x",
            ),
            None,
        )

    monkeypatch.setattr(service._classifier, "classify", fake_classify)


def _make_fake_loaded(file_path: Path) -> LoadedDocument:
    return LoadedDocument(
        path=file_path,
        content="ignored content",
        page_count=1,
        pages_sampled=1,
        mime_type="text/plain",
        loader_latency_ms=1.0,
        loader_backend="docling",
    )


async def test_debug_structure_dump_structure_called_during_load(
    tmp_path: Path,
) -> None:
    """DoclingLoader.dump_structure writes the docling.json when debug_structure=True."""
    debug_dir = tmp_path / "debug"
    debug_dir.mkdir()

    sample_payload = {"name": "fake_doc", "tables": []}

    def _md(**_kwargs: object) -> str:
        return "# content"

    fake_doc = SimpleNamespace(
        export_to_markdown=_md,
        export_to_dict=lambda: sample_payload,
        pages={1: SimpleNamespace()},
    )
    fake_result = SimpleNamespace(document=fake_doc)

    class FakeConverter:
        def convert(self, source: str) -> SimpleNamespace:
            return fake_result

    source_path = tmp_path / "sample.txt"
    source_path.write_text("payload")

    loader = DoclingLoader(
        debug_dir=debug_dir,
        debug_structure=True,
    )

    with (
        patch("drover.loader._build_docling_converter", return_value=FakeConverter()),
        patch("drover.loader._check_docling_models_available"),
    ):
        loaded = await loader.load(source_path)

    assert loaded.loader_backend == "docling"
    out = debug_dir / "sample.docling.json"
    assert out.exists(), f"Expected {out} to be written by dump_structure"
    assert json.loads(out.read_text()) == sample_payload


async def test_debug_structure_not_written_when_flag_off(
    tmp_path: Path,
) -> None:
    """DoclingLoader does not write a structure dump when debug_structure=False."""
    debug_dir = tmp_path / "debug"
    debug_dir.mkdir()

    sample_payload = {"name": "fake_doc"}

    def _md2(**_kwargs: object) -> str:
        return "# content"

    fake_doc = SimpleNamespace(
        export_to_markdown=_md2,
        export_to_dict=lambda: sample_payload,
        pages={1: SimpleNamespace()},
    )
    fake_result = SimpleNamespace(document=fake_doc)

    class FakeConverter:
        def convert(self, source: str) -> SimpleNamespace:
            return fake_result

    source_path = tmp_path / "sample.txt"
    source_path.write_text("payload")

    loader = DoclingLoader(
        debug_dir=debug_dir,
        debug_structure=False,
    )

    with (
        patch("drover.loader._build_docling_converter", return_value=FakeConverter()),
        patch("drover.loader._check_docling_models_available"),
    ):
        await loader.load(source_path)

    assert not list(debug_dir.glob("*.docling.json"))


async def test_debug_structure_no_op_for_unstructured_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The unstructured loader never writes a structure dump."""
    from drover.models import ClassificationResult
    from drover.service import ClassificationService

    debug_dir = tmp_path / "debug"
    cfg = DroverConfig(
        loader=LoaderType.UNSTRUCTURED,
        debug_structure=True,
        debug_dir=debug_dir,
    )
    service = ClassificationService(cfg)
    _patch_classifier(service, monkeypatch)

    file_path = tmp_path / "sample.txt"
    file_path.write_text("payload")

    async def fake_load(path: Path) -> LoadedDocument:
        return _make_fake_loaded(path)

    monkeypatch.setattr(service._loader, "load", fake_load)

    result = await service.classify_file(file_path)

    assert isinstance(result, ClassificationResult)
    assert not debug_dir.exists() or not list(debug_dir.glob("*.docling.json"))
