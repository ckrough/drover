"""Tests for DocumentLoader and document sampling."""

from pathlib import Path

import pytest

from drover.loader import DocumentLoader
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
