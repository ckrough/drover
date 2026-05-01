"""Document loading with unstructured library integration.

Supports PDF, images, Office documents, and text files with configurable
sampling strategies for handling large documents efficiently.
"""

import asyncio
import mimetypes
import os
import time
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

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


@runtime_checkable
class DoclingDocumentLike(Protocol):
    """Protocol for a parsed Docling document."""

    def export_to_markdown(self, **kwargs: object) -> str: ...


@runtime_checkable
class DocumentLoaderProtocol(Protocol):
    """Common interface shared by all loader backends."""

    async def load(self, path: Path) -> "LoadedDocument": ...


class LoadedDocument(BaseModel):
    """Result of loading a document."""

    path: Path
    content: str = Field(description="Extracted text content")
    page_count: int = Field(default=1, description="Total pages in document")
    pages_sampled: int = Field(default=1, description="Pages actually processed")
    mime_type: str | None = Field(default=None, description="Detected MIME type")
    loader_latency_ms: float | None = Field(
        default=None,
        description="Wallclock duration of the loader's parse call, in ms",
    )
    loader_backend: str | None = Field(
        default=None,
        description="Loader backend identifier (unstructured | docling)",
    )


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

# Standard Docling model cache location
_DOCLING_MODEL_CACHE = Path.home() / ".cache" / "docling" / "models"


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
    """Build a Docling `DocumentConverter` with full-page OCR enabled.

    Full-page OCR overlays recognized text across the entire page,
    including logos and embedded graphics that text-layer extraction
    cannot see. Rationale and trade-offs: docs/adr/005-docling-evaluation.md.
    """
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options.force_full_page_ocr = True

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)
        }
    )


def _check_docling_models_available() -> None:
    """Verify the Docling model cache exists and is non-empty.

    Raises:
        DocumentLoadError: If models are not present, with an actionable message.
    """
    if not _DOCLING_MODEL_CACHE.exists() or not any(_DOCLING_MODEL_CACHE.iterdir()):
        raise DocumentLoadError(
            f"Docling models not found at {_DOCLING_MODEL_CACHE}. Run:\n"
            "  uv run docling-tools models download\n"
            "First-run setup is documented in CONTRIBUTING.md."
        )


class DoclingLoader:
    """Structure-aware document loader backed by Docling.

    Converts PDF and other documents using Docling's full-page OCR pipeline
    and returns a `LoadedDocument` whose `content` is the markdown export,
    ready for use as LLM prompt input. Page sampling is applied before
    export to keep prompt size bounded.
    """

    _SMALL_DOC_PAGES = 5
    _MEDIUM_DOC_PAGES = 20

    def __init__(
        self,
        strategy: SampleStrategy = SampleStrategy.ADAPTIVE,
        max_pages: int = 10,
        debug_dir: Path | None = None,
        debug_structure: bool = False,
    ) -> None:
        """Initialize DoclingLoader.

        Args:
            strategy: Sampling strategy for large documents.
            max_pages: Maximum pages to include in the markdown export.
            debug_dir: Optional directory for debug structure dumps.
            debug_structure: When True, write a .docling.json structure file
                alongside each loaded document.
        """
        self.strategy = strategy
        self.max_pages = max_pages
        self.debug_dir = debug_dir
        self.debug_structure = debug_structure

    async def load(self, path: Path) -> LoadedDocument:
        """Load a document via Docling with page sampling.

        Converts the document using Docling's full-page OCR pipeline, selects
        a subset of pages via the configured sampling strategy, then exports
        only those pages as markdown for use as LLM prompt input.

        Args:
            path: Path to document file.

        Returns:
            LoadedDocument with markdown content derived from sampled pages.

        Raises:
            DocumentLoadError: If loading fails, the docling extra is not
                installed, or the Docling model cache is absent.
        """
        if not path.exists():
            raise DocumentLoadError(f"File not found: {path}")

        suffix = path.suffix.lower()
        mime_type, _ = mimetypes.guess_type(str(path))

        if suffix not in _SUPPORTED_EXTENSIONS:
            raise DocumentLoadError(f"Unsupported file type: {suffix}")

        try:
            _check_docling_models_available()
            converter = _build_docling_converter()
        except DocumentLoadError:
            raise
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

        # Determine page count from the pages dict (keys are 1-based page numbers)
        pages_dict: dict[int, Any] = getattr(document, "pages", {}) or {}
        page_count = len(pages_dict) if pages_dict else 1

        # Select which page numbers to export
        sampled_page_nos = self._select_page_numbers(page_count)
        pages_sampled = len(sampled_page_nos)

        # Export only the sampled pages
        if pages_sampled < page_count and pages_dict:
            parts = [
                document.export_to_markdown(page_no=pno) for pno in sampled_page_nos
            ]
            markdown = "\n\n".join(p for p in parts if p.strip())
        else:
            markdown = document.export_to_markdown()

        if not markdown.strip():
            raise DocumentLoadError(f"No text content found in {path.name}")

        if self.debug_structure:
            self.dump_structure(document, path)

        return LoadedDocument(
            path=path,
            content=markdown,
            page_count=page_count,
            pages_sampled=pages_sampled,
            mime_type=mime_type,
            loader_latency_ms=loader_latency_ms,
            loader_backend="docling",
        )

    def _select_page_numbers(self, total_pages: int) -> list[int]:
        """Return the 1-based page numbers to export, applying the sampling strategy.

        Args:
            total_pages: Total number of pages in the document.

        Returns:
            Ordered list of 1-based page numbers to export.
        """
        all_pages = list(range(1, total_pages + 1))

        if total_pages <= self.max_pages:
            return all_pages

        effective_strategy = self._select_strategy(total_pages)

        match effective_strategy:
            case SampleStrategy.FULL:
                return all_pages
            case SampleStrategy.FIRST_N:
                return all_pages[: self.max_pages]
            case SampleStrategy.BOOKENDS:
                half = self.max_pages // 2
                return all_pages[:half] + all_pages[-half:]
            case _:
                return all_pages[: self.max_pages]

    def _select_strategy(self, total_pages: int) -> SampleStrategy:
        """Select effective strategy based on document size.

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

    def dump_structure(self, document: DoclingDocumentLike, source_path: Path) -> None:
        """Write the parsed DoclingDocument structure to a .docling.json file.

        Args:
            document: The parsed Docling document.
            source_path: Path to the original source document (used for naming).
        """
        import json

        export_to_dict = getattr(document, "export_to_dict", None)
        if export_to_dict is None:
            return

        if self.debug_dir is not None:
            debug_root = self.debug_dir.expanduser()
            debug_root.mkdir(parents=True, exist_ok=True)
            base = debug_root / source_path.stem
        else:
            base = source_path.with_suffix("")

        target = _unique_path(base.with_suffix(".docling.json"))
        target.write_text(json.dumps(export_to_dict(), indent=2))


def _unique_path(base: Path) -> Path:
    """Return a unique path by appending a numeric suffix if needed."""
    if not base.exists():
        return base

    idx = 1
    while True:
        candidate = base.with_name(f"{base.stem}_{idx}{base.suffix}")
        if not candidate.exists():
            return candidate
        idx += 1
