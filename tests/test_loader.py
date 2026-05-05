"""Tests for DoclingLoader and document sampling."""

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from drover.loader import (
    _SUPPORTED_EXTENSIONS,
    DoclingLoader,
    DocumentLoadError,
)
from drover.sampling import SampleStrategy


def test_supported_extensions_match_docling_audit() -> None:
    """`_SUPPORTED_EXTENSIONS` matches Docling's officially-supported set.

    Source: https://docling-project.github.io/docling/usage/supported_formats/
    Locked here so accidental additions surface as test failures and get
    a deliberate review against the upstream support table.
    """
    expected = {
        ".pdf",
        ".txt",
        ".md",
        ".html",
        ".htm",
        ".csv",
        ".docx",
        ".xlsx",
        ".pptx",
        ".png",
        ".jpg",
        ".jpeg",
        ".tiff",
        ".tif",
        ".bmp",
    }
    assert expected == _SUPPORTED_EXTENSIONS

    # Formats removed per ADR-006 (not in Docling's supported set):
    for unsupported in {
        ".doc",
        ".xls",
        ".ppt",  # legacy MS Office (Open XML only)
        ".gif",  # not in Docling's image set
        ".tsv",  # Docling lists CSV only
        ".eml",
        ".epub",
        ".odt",
        ".rtf",  # never reliably handled
    }:
        assert unsupported not in _SUPPORTED_EXTENSIONS


# ---------------------------------------------------------------------------
# DoclingLoader
# ---------------------------------------------------------------------------


def _fake_docling_result(markdown: str, num_pages: int = 1) -> SimpleNamespace:
    """Build a stand-in for `ConversionResult` with the attributes we use."""
    _md = markdown

    def _export(**_kwargs: object) -> str:
        return _md

    document = SimpleNamespace(
        export_to_markdown=_export,
        pages={i: SimpleNamespace() for i in range(1, num_pages + 1)},
    )
    return SimpleNamespace(document=document)


async def test_docling_loader_loads_document(tmp_path: Path) -> None:
    """DoclingLoader returns content from the markdown export."""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("placeholder body for docling fake")

    fake_result = _fake_docling_result("# Heading\n\nBody.", num_pages=2)

    class FakeConverter:
        def convert(self, source: str) -> SimpleNamespace:
            return fake_result

    with (
        patch("drover.loader._build_docling_converter", return_value=FakeConverter()),
        patch("drover.loader._check_docling_models_available"),
    ):
        loader = DoclingLoader()
        loaded = await loader.load(file_path)

    assert loaded.path == file_path
    assert loaded.content == "# Heading\n\nBody."
    assert loaded.page_count == 2
    assert loaded.loader_backend == "docling"
    assert loaded.loader_latency_ms is not None
    assert loaded.loader_latency_ms >= 0.0


async def test_docling_loader_raises_when_package_missing(tmp_path: Path) -> None:
    """A clear error fires when the `docling` extra is not installed."""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("body")

    def boom() -> None:
        raise ImportError("docling not installed")

    with patch("drover.loader._build_docling_converter", side_effect=boom):
        loader = DoclingLoader()
        with pytest.raises(DocumentLoadError, match="docling"):
            await loader.load(file_path)


async def test_docling_loader_rejects_unsupported_extension(tmp_path: Path) -> None:
    """DoclingLoader rejects unsupported extensions before invoking Docling."""
    file_path = tmp_path / "data.xyz"
    file_path.write_text("noop")

    loader = DoclingLoader()
    with pytest.raises(DocumentLoadError, match="Unsupported file type"):
        await loader.load(file_path)


async def test_docling_loader_raises_for_missing_file(tmp_path: Path) -> None:
    """Missing files produce DocumentLoadError before any docling call."""
    loader = DoclingLoader()
    with pytest.raises(DocumentLoadError, match="File not found"):
        await loader.load(tmp_path / "ghost.pdf")


async def test_docling_loader_raises_when_markdown_empty(tmp_path: Path) -> None:
    """An empty markdown export is treated as a failed load."""
    file_path = tmp_path / "empty.txt"
    file_path.write_text("placeholder")

    fake_result = _fake_docling_result("   \n", num_pages=1)

    class FakeConverter:
        def convert(self, source: str) -> SimpleNamespace:
            return fake_result

    with (
        patch("drover.loader._build_docling_converter", return_value=FakeConverter()),
        patch("drover.loader._check_docling_models_available"),
    ):
        loader = DoclingLoader()
        with pytest.raises(DocumentLoadError, match="No text content"):
            await loader.load(file_path)


async def test_docling_loader_raises_when_models_missing(tmp_path: Path) -> None:
    """DoclingLoader raises DocumentLoadError when model cache is absent."""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("body")

    with patch(
        "drover.loader._check_docling_models_available",
        side_effect=DocumentLoadError("Docling models not found"),
    ):
        loader = DoclingLoader()
        with pytest.raises(DocumentLoadError, match="Docling models not found"):
            await loader.load(file_path)


def test_docling_loader_page_sampling_first_n() -> None:
    """DoclingLoader._select_page_numbers respects FIRST_N strategy."""
    loader = DoclingLoader(strategy=SampleStrategy.FIRST_N, max_pages=3)
    page_nos = loader._select_page_numbers(10)
    assert page_nos == [1, 2, 3]


def test_docling_loader_page_sampling_bookends() -> None:
    """DoclingLoader._select_page_numbers applies BOOKENDS correctly."""
    loader = DoclingLoader(strategy=SampleStrategy.BOOKENDS, max_pages=4)
    page_nos = loader._select_page_numbers(10)
    assert page_nos == [1, 2, 9, 10]


def test_docling_loader_page_sampling_returns_all_when_under_max() -> None:
    """DoclingLoader returns all pages when document is smaller than max_pages."""
    loader = DoclingLoader(strategy=SampleStrategy.FIRST_N, max_pages=10)
    page_nos = loader._select_page_numbers(3)
    assert page_nos == [1, 2, 3]


async def test_docling_loader_pages_sampled_matches_selected(tmp_path: Path) -> None:
    """pages_sampled reflects the actual number of sampled pages, not total."""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("placeholder")

    # 15-page doc; FIRST_N with max_pages=5 → 5 pages sampled
    fake_result = _fake_docling_result("content", num_pages=15)

    class FakeConverter:
        def convert(self, source: str) -> SimpleNamespace:
            return fake_result

    with (
        patch("drover.loader._build_docling_converter", return_value=FakeConverter()),
        patch("drover.loader._check_docling_models_available"),
    ):
        loader = DoclingLoader(strategy=SampleStrategy.FIRST_N, max_pages=5)
        loaded = await loader.load(file_path)

    assert loaded.page_count == 15
    assert loaded.pages_sampled == 5


# ---------------------------------------------------------------------------
# P1-5: BOOKENDS odd max_pages — DoclingLoader._select_page_numbers
# ---------------------------------------------------------------------------


def test_docling_loader_bookends_odd_max_pages_3() -> None:
    """BOOKENDS with max_pages=3 should return 3 pages (2 head + 1 tail)."""
    loader = DoclingLoader(strategy=SampleStrategy.BOOKENDS, max_pages=3)
    page_nos = loader._select_page_numbers(10)
    assert len(page_nos) == 3
    assert page_nos == [1, 2, 10]


def test_docling_loader_bookends_odd_max_pages_5() -> None:
    """BOOKENDS with max_pages=5 should return 5 pages (3 head + 2 tail)."""
    loader = DoclingLoader(strategy=SampleStrategy.BOOKENDS, max_pages=5)
    page_nos = loader._select_page_numbers(20)
    assert len(page_nos) == 5
    assert page_nos == [1, 2, 3, 19, 20]


def test_docling_loader_bookends_even_max_pages_4() -> None:
    """BOOKENDS with even max_pages=4 stays 2+2 (regression guard)."""
    loader = DoclingLoader(strategy=SampleStrategy.BOOKENDS, max_pages=4)
    page_nos = loader._select_page_numbers(10)
    assert len(page_nos) == 4
    assert page_nos == [1, 2, 9, 10]


# ---------------------------------------------------------------------------
# P1-3: dump_structure falls back to cwd/debug when debug_dir is None
# ---------------------------------------------------------------------------


def test_dump_structure_fallback_uses_cwd_debug(tmp_path: Path) -> None:
    """dump_structure without debug_dir writes into cwd/debug/, not source dir."""
    import os

    source_file = tmp_path / "doc.pdf"
    source_file.write_text("placeholder")

    def fake_export_to_dict() -> dict[str, object]:
        return {"key": "value"}

    document = SimpleNamespace(
        export_to_markdown=lambda: "md",
        export_to_dict=fake_export_to_dict,
    )

    loader = DoclingLoader(debug_dir=None)

    # Run from tmp_path so cwd is predictable
    original_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        loader.dump_structure(document, source_file)
        expected_dir = tmp_path / "debug"
        assert expected_dir.is_dir(), "debug/ directory should have been created"
        json_files = list(expected_dir.glob("*.docling.json"))
        assert len(json_files) == 1
        # Confirm source directory is clean (no .docling.json next to source)
        assert not list(tmp_path.glob("*.docling.json"))
    finally:
        os.chdir(original_cwd)


def test_dump_structure_explicit_debug_dir(tmp_path: Path) -> None:
    """dump_structure with explicit debug_dir writes there."""
    debug_dir = tmp_path / "my_debug"
    source_file = tmp_path / "doc.pdf"
    source_file.write_text("placeholder")

    def fake_export_to_dict() -> dict[str, object]:
        return {"hello": "world"}

    document = SimpleNamespace(export_to_dict=fake_export_to_dict)
    loader = DoclingLoader(debug_dir=debug_dir)
    loader.dump_structure(document, source_file)

    json_files = list(debug_dir.glob("*.docling.json"))
    assert len(json_files) == 1
    data = json.loads(json_files[0].read_text())
    assert data == {"hello": "world"}


# ---------------------------------------------------------------------------
# P1-3: OSError from dump_structure is caught; load still returns content
# ---------------------------------------------------------------------------


async def test_docling_loader_debug_write_oserror_does_not_abort_load(
    tmp_path: Path,
) -> None:
    """An OSError during debug structure write must not abort the load."""
    file_path = tmp_path / "sample.txt"
    file_path.write_text("placeholder")

    fake_result = _fake_docling_result("# Content", num_pages=1)

    class FakeConverter:
        def convert(self, source: str) -> SimpleNamespace:
            return fake_result

    def bad_dump_structure(document: object, source_path: Path) -> None:
        raise OSError("read-only filesystem")

    with (
        patch("drover.loader._build_docling_converter", return_value=FakeConverter()),
        patch("drover.loader._check_docling_models_available"),
        patch.object(DoclingLoader, "dump_structure", side_effect=bad_dump_structure),
    ):
        loader = DoclingLoader(debug_structure=True)
        loaded = await loader.load(file_path)

    # Load should succeed despite the OSError
    assert "Content" in loaded.content
