"""Tests for --debug-structure dumps (prof-rbz)."""

from __future__ import annotations

import json
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest

from drover.config import DroverConfig, LoaderType
from drover.loader import LoadedDocument
from drover.models import ClassificationResult
from drover.service import ClassificationService

if TYPE_CHECKING:
    from pathlib import Path


def _patch_classifier(service: ClassificationService, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Replace the classifier with a no-op fake so tests stay LLM-free."""

    async def fake_classify(
        content: str,
        capture_debug: bool = False,
        collect_metrics: bool = False,
        docling_doc: object | None = None,
    ):
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


def _stub_loaded_doc(file_path: Path, docling_doc: object | None) -> LoadedDocument:
    return LoadedDocument(
        path=file_path,
        content="ignored",
        page_count=1,
        pages_sampled=1,
        mime_type="text/plain",
        docling_doc=docling_doc,
        loader_latency_ms=1.0,
        loader_backend="docling" if docling_doc is not None else "unstructured",
    )


@pytest.mark.asyncio
async def test_debug_structure_writes_docling_json(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the docling loader is active, the parsed doc is dumped to disk."""
    debug_dir = tmp_path / "debug"
    cfg = DroverConfig(
        loader=LoaderType.DOCLING,
        debug_structure=True,
        debug_dir=debug_dir,
    )
    service = ClassificationService(cfg)
    _patch_classifier(service, monkeypatch)

    sample_payload = {"name": "fake_doc", "tables": []}
    fake_doc = SimpleNamespace(export_to_dict=lambda: sample_payload)

    file_path = tmp_path / "sample.txt"
    file_path.write_text("payload")

    async def fake_load(path: Path) -> LoadedDocument:
        return _stub_loaded_doc(path, fake_doc)

    monkeypatch.setattr(service._loader, "load", fake_load)

    result = await service.classify_file(file_path)

    assert isinstance(result, ClassificationResult)
    out = debug_dir / "sample.docling.json"
    assert out.exists()
    assert json.loads(out.read_text()) == sample_payload


@pytest.mark.asyncio
async def test_debug_structure_no_op_for_unstructured_loader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Without a docling_doc the flag becomes a no-op (no file written)."""
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
        return _stub_loaded_doc(path, docling_doc=None)

    monkeypatch.setattr(service._loader, "load", fake_load)

    await service.classify_file(file_path)

    assert not debug_dir.exists() or not list(debug_dir.glob("*.docling.json"))


@pytest.mark.asyncio
async def test_debug_structure_off_when_flag_not_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Default behavior writes nothing even when a docling_doc is available."""
    debug_dir = tmp_path / "debug"
    cfg = DroverConfig(
        loader=LoaderType.DOCLING,
        debug_structure=False,
        debug_dir=debug_dir,
    )
    service = ClassificationService(cfg)
    _patch_classifier(service, monkeypatch)

    fake_doc = SimpleNamespace(export_to_dict=lambda: {"name": "fake"})
    file_path = tmp_path / "sample.txt"
    file_path.write_text("payload")

    async def fake_load(path: Path) -> LoadedDocument:
        return _stub_loaded_doc(path, fake_doc)

    monkeypatch.setattr(service._loader, "load", fake_load)

    await service.classify_file(file_path)

    assert not debug_dir.exists() or not list(debug_dir.glob("*.docling.json"))
