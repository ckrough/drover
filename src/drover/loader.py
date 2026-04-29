"""Document loading with unstructured library integration.

Supports PDF, images, Office documents, and text files with configurable
sampling strategies for handling large documents efficiently.
"""

import asyncio
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

# Disable unstructured telemetry and auto-downloads BEFORE importing the library.
# This prevents network calls to packages.unstructured.io (Scarf analytics)
# and NLTK data servers. Both DO_NOT_TRACK and SCARF_NO_ANALYTICS are required
# to fully disable telemetry. See: https://github.com/Unstructured-IO/unstructured/issues/3459
os.environ.setdefault("DO_NOT_TRACK", "true")
os.environ.setdefault("SCARF_NO_ANALYTICS", "true")
os.environ.setdefault("AUTO_DOWNLOAD_NLTK", "false")

from pydantic import BaseModel, Field
from unstructured.partition.auto import partition

from drover.sampling import SampleStrategy


class LoadedDocument(BaseModel):
    """Result of loading a document."""

    path: Path
    content: str = Field(description="Extracted text content")
    page_count: int = Field(default=1, description="Total pages in document")
    pages_sampled: int = Field(default=1, description="Pages actually processed")
    mime_type: str | None = Field(default=None, description="Detected MIME type")
    docling_doc: Any | None = Field(
        default=None,
        description="Parsed DoclingDocument when loader=docling, else None",
    )
    loader_latency_ms: float | None = Field(
        default=None,
        description="Wallclock duration of the loader's parse call, in ms",
    )
    loader_backend: str | None = Field(
        default=None,
        description="Loader backend identifier (unstructured | docling)",
    )

    model_config = {"arbitrary_types_allowed": True}


class DocumentLoadError(Exception):
    """Raised when document loading fails."""

    pass


# Supported file extensions for validation
_SUPPORTED_EXTENSIONS: set[str] = {
    # PDF
    ".pdf",
    # Text
    ".txt",
    ".md",
    # Images
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".tiff",
    ".tif",
    # Office documents
    ".docx",
    ".doc",
    ".xlsx",
    ".xls",
    ".pptx",
    ".ppt",
    # Other
    ".html",
    ".htm",
    ".csv",
    ".tsv",
    ".eml",
    ".epub",
    ".odt",
    ".rtf",
}


class DocumentLoader:
    """Loads and samples documents for classification.

    Supports multiple file types and sampling strategies to
    efficiently handle large documents.
    """

    _SMALL_DOC_PAGES = 5
    _MEDIUM_DOC_PAGES = 20

    def __init__(
        self,
        strategy: SampleStrategy = SampleStrategy.ADAPTIVE,
        max_pages: int = 10,
    ) -> None:
        """Initialize document loader.

        Args:
            strategy: Sampling strategy for large documents.
            max_pages: Maximum pages to process.
        """
        self.strategy = strategy
        self.max_pages = max_pages

    async def load(self, path: Path) -> LoadedDocument:
        """Load a document and extract text content.

        Args:
            path: Path to document file.

        Returns:
            LoadedDocument with extracted content.

        Raises:
            DocumentLoadError: If loading fails.
        """
        if not path.exists():
            raise DocumentLoadError(f"File not found: {path}")

        suffix = path.suffix.lower()
        mime_type, _ = mimetypes.guess_type(str(path))

        if suffix not in _SUPPORTED_EXTENSIONS:
            raise DocumentLoadError(f"Unsupported file type: {suffix}")

        start = time.perf_counter()
        try:
            elements = await asyncio.to_thread(partition, filename=str(path))
        except Exception as e:
            raise DocumentLoadError(f"Failed to load {path.name}: {e}") from e
        loader_latency_ms = (time.perf_counter() - start) * 1000.0

        if not elements:
            raise DocumentLoadError(f"No content extracted from {path.name}")

        # Group elements by page number for sampling
        pages = self._group_by_page(elements)
        total_pages = len(pages) if pages else 1

        # Apply sampling strategy
        sampled_pages = self._apply_sampling(pages, total_pages)

        # Extract text from sampled pages
        content = self._extract_text(sampled_pages)

        if not content.strip():
            raise DocumentLoadError(f"No text content found in {path.name}")

        return LoadedDocument(
            path=path,
            content=content,
            page_count=total_pages,
            pages_sampled=len(sampled_pages),
            mime_type=mime_type,
            loader_latency_ms=loader_latency_ms,
            loader_backend="unstructured",
        )

    def _group_by_page(self, elements: list[Any]) -> list[list[Any]]:
        """Group elements by their page number.

        Args:
            elements: List of unstructured elements.

        Returns:
            List of element groups, one per page.
        """
        if not elements:
            return []

        pages: dict[int, list[Any]] = {}
        for el in elements:
            page_num = getattr(el.metadata, "page_number", 1) or 1
            if page_num not in pages:
                pages[page_num] = []
            pages[page_num].append(el)

        # Return pages in order
        if not pages:
            return [list(elements)]

        max_page = max(pages.keys())
        return [pages.get(i, []) for i in range(1, max_page + 1) if pages.get(i)]

    def _extract_text(self, pages: list[list[Any]]) -> str:
        """Extract text content from grouped elements.

        Args:
            pages: List of element groups by page.

        Returns:
            Combined text content.
        """
        texts = []
        for page_elements in pages:
            page_text = "\n".join(str(el) for el in page_elements if str(el).strip())
            if page_text.strip():
                texts.append(page_text)
        return "\n\n".join(texts)

    def _apply_sampling(
        self, pages: list[list[Any]], total_pages: int
    ) -> list[list[Any]]:
        """Apply sampling strategy to document pages.

        Args:
            pages: All loaded document pages.
            total_pages: Total number of pages.

        Returns:
            Sampled subset of pages.
        """
        if total_pages <= self.max_pages:
            return pages

        effective_strategy = self._select_strategy(total_pages)

        match effective_strategy:
            case SampleStrategy.FULL:
                return pages
            case SampleStrategy.FIRST_N:
                return pages[: self.max_pages]
            case SampleStrategy.BOOKENDS:
                half = self.max_pages // 2
                return pages[:half] + pages[-half:]
            case _:
                return pages[: self.max_pages]

    def _select_strategy(self, total_pages: int) -> SampleStrategy:
        """Select effective strategy based on document size.

        For adaptive mode, chooses strategy based on page count.

        Args:
            total_pages: Total pages in document.

        Returns:
            Effective sampling strategy.
        """
        if self.strategy != SampleStrategy.ADAPTIVE:
            return self.strategy

        if total_pages <= self._SMALL_DOC_PAGES:
            return SampleStrategy.FULL
        elif total_pages <= self._MEDIUM_DOC_PAGES:
            return SampleStrategy.FIRST_N
        else:
            return SampleStrategy.BOOKENDS


async def load_document(
    path: Path,
    strategy: SampleStrategy = SampleStrategy.ADAPTIVE,
    max_pages: int = 10,
) -> LoadedDocument:
    """Convenience function to load a single document.

    Args:
        path: Path to document file.
        strategy: Sampling strategy.
        max_pages: Maximum pages to process.

    Returns:
        LoadedDocument with extracted content.
    """
    loader = DocumentLoader(strategy=strategy, max_pages=max_pages)
    return await loader.load(path)


def _build_docling_converter() -> Any:
    """Build a Docling `DocumentConverter`. Isolated to ease testing/mocking."""
    from docling.document_converter import DocumentConverter

    return DocumentConverter()


class DoclingLoader:
    """Structure-aware document loader backed by Docling.

    Returns a `LoadedDocument` whose `content` is the markdown export (so
    every existing consumer keeps working) and whose `docling_doc` field
    carries the parsed `DoclingDocument` for downstream structure-aware
    pipelines (LLM prompts with headings, NLI HybridChunker, region-targeted
    metadata extraction).
    """

    def __init__(
        self,
        strategy: SampleStrategy = SampleStrategy.ADAPTIVE,
        max_pages: int = 10,
    ) -> None:
        self.strategy = strategy
        self.max_pages = max_pages

    async def load(self, path: Path) -> LoadedDocument:
        """Load a document via Docling and return a `LoadedDocument`.

        Args:
            path: Path to document file.

        Returns:
            LoadedDocument with markdown content and parsed structure.

        Raises:
            DocumentLoadError: If loading fails or the docling extra is
                not installed.
        """
        if not path.exists():
            raise DocumentLoadError(f"File not found: {path}")

        suffix = path.suffix.lower()
        mime_type, _ = mimetypes.guess_type(str(path))

        if suffix not in _SUPPORTED_EXTENSIONS:
            raise DocumentLoadError(f"Unsupported file type: {suffix}")

        try:
            converter = _build_docling_converter()
        except ImportError as e:
            raise DocumentLoadError(
                "docling is not installed. Install with `uv sync --extra docling`."
            ) from e

        start = time.perf_counter()
        try:
            result = await asyncio.to_thread(converter.convert, str(path))
        except Exception as e:
            raise DocumentLoadError(f"Failed to load {path.name}: {e}") from e
        loader_latency_ms = (time.perf_counter() - start) * 1000.0

        document = getattr(result, "document", None)
        if document is None:
            raise DocumentLoadError(f"No content extracted from {path.name}")

        markdown = document.export_to_markdown()
        if not markdown.strip():
            raise DocumentLoadError(f"No text content found in {path.name}")

        pages = getattr(document, "pages", None)
        page_count = len(pages) if pages else 1

        return LoadedDocument(
            path=path,
            content=markdown,
            page_count=page_count,
            pages_sampled=page_count,
            mime_type=mime_type,
            docling_doc=document,
            loader_latency_ms=loader_latency_ms,
            loader_backend="docling",
        )
