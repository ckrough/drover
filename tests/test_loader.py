"""Tests for DocumentLoader and document sampling."""

from pathlib import Path

import pytest

from drover.loader import (
    _SUPPORTED_EXTENSIONS,
    DocumentLoader,
    DocumentLoadError,
)
from drover.sampling import SampleStrategy


@pytest.mark.asyncio
async def test_document_loader_loads_text_file(tmp_path: Path) -> None:
    """DocumentLoader should load a simple text file without errors."""
    file_path = tmp_path / "example.txt"
    file_path.write_text("hello world")

    loader = DocumentLoader(strategy=SampleStrategy.FULL, max_pages=10)
    loaded = await loader.load(file_path)

    assert loaded.path == file_path
    assert "hello world" in loaded.content
    assert loaded.page_count == 1
    assert loaded.pages_sampled == 1


@pytest.mark.asyncio
async def test_document_loader_loads_markdown_file(tmp_path: Path) -> None:
    """DocumentLoader should load markdown files."""
    file_path = tmp_path / "readme.md"
    file_path.write_text("# Header\n\nSome content here.")

    loader = DocumentLoader(strategy=SampleStrategy.FULL, max_pages=10)
    loaded = await loader.load(file_path)

    assert loaded.path == file_path
    assert "Header" in loaded.content
    assert "Some content" in loaded.content


@pytest.mark.asyncio
async def test_document_loader_raises_for_missing_file(tmp_path: Path) -> None:
    """DocumentLoader should raise DocumentLoadError for missing files."""
    file_path = tmp_path / "nonexistent.txt"

    loader = DocumentLoader()
    with pytest.raises(DocumentLoadError, match="File not found"):
        await loader.load(file_path)


@pytest.mark.asyncio
async def test_document_loader_raises_for_unsupported_type(tmp_path: Path) -> None:
    """DocumentLoader should raise DocumentLoadError for unsupported file types."""
    file_path = tmp_path / "data.xyz"
    file_path.write_text("some data")

    loader = DocumentLoader()
    with pytest.raises(DocumentLoadError, match="Unsupported file type"):
        await loader.load(file_path)


@pytest.mark.asyncio
async def test_document_loader_raises_for_empty_file(tmp_path: Path) -> None:
    """DocumentLoader should raise DocumentLoadError for empty files."""
    file_path = tmp_path / "empty.txt"
    file_path.write_text("")

    loader = DocumentLoader()
    with pytest.raises(DocumentLoadError):
        await loader.load(file_path)


def test_supported_extensions_include_common_types() -> None:
    """Supported extensions should include common document types."""
    assert ".pdf" in _SUPPORTED_EXTENSIONS
    assert ".txt" in _SUPPORTED_EXTENSIONS
    assert ".md" in _SUPPORTED_EXTENSIONS
    assert ".docx" in _SUPPORTED_EXTENSIONS
    assert ".xlsx" in _SUPPORTED_EXTENSIONS
    assert ".pptx" in _SUPPORTED_EXTENSIONS
    assert ".png" in _SUPPORTED_EXTENSIONS
    assert ".jpg" in _SUPPORTED_EXTENSIONS


def test_sampling_strategy_first_n() -> None:
    """FIRST_N strategy should return first N pages."""
    loader = DocumentLoader(strategy=SampleStrategy.FIRST_N, max_pages=3)

    # Create mock pages (list of lists)
    pages = [[f"page{i}"] for i in range(10)]
    sampled = loader._apply_sampling(pages, total_pages=10)

    assert len(sampled) == 3
    assert sampled == [["page0"], ["page1"], ["page2"]]


def test_sampling_strategy_bookends() -> None:
    """BOOKENDS strategy should return first and last pages."""
    loader = DocumentLoader(strategy=SampleStrategy.BOOKENDS, max_pages=4)

    pages = [[f"page{i}"] for i in range(10)]
    sampled = loader._apply_sampling(pages, total_pages=10)

    assert len(sampled) == 4
    # First 2 and last 2
    assert sampled == [["page0"], ["page1"], ["page8"], ["page9"]]


def test_sampling_strategy_full() -> None:
    """FULL strategy should return all pages regardless of max_pages."""
    loader = DocumentLoader(strategy=SampleStrategy.FULL, max_pages=3)

    pages = [[f"page{i}"] for i in range(5)]
    sampled = loader._apply_sampling(pages, total_pages=5)

    assert len(sampled) == 5


def test_sampling_returns_all_when_under_max() -> None:
    """Should return all pages when document is smaller than max_pages."""
    loader = DocumentLoader(strategy=SampleStrategy.FIRST_N, max_pages=10)

    pages = [[f"page{i}"] for i in range(3)]
    sampled = loader._apply_sampling(pages, total_pages=3)

    assert len(sampled) == 3


def test_adaptive_strategy_selects_full_for_small_docs() -> None:
    """ADAPTIVE should use FULL for documents <= 5 pages."""
    loader = DocumentLoader(strategy=SampleStrategy.ADAPTIVE, max_pages=10)

    selected = loader._select_strategy(total_pages=5)
    assert selected == SampleStrategy.FULL


def test_adaptive_strategy_selects_first_n_for_medium_docs() -> None:
    """ADAPTIVE should use FIRST_N for documents 6-20 pages."""
    loader = DocumentLoader(strategy=SampleStrategy.ADAPTIVE, max_pages=10)

    selected = loader._select_strategy(total_pages=15)
    assert selected == SampleStrategy.FIRST_N


def test_adaptive_strategy_selects_bookends_for_large_docs() -> None:
    """ADAPTIVE should use BOOKENDS for documents > 20 pages."""
    loader = DocumentLoader(strategy=SampleStrategy.ADAPTIVE, max_pages=10)

    selected = loader._select_strategy(total_pages=50)
    assert selected == SampleStrategy.BOOKENDS
