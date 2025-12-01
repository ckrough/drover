"""Document loading with LangChain integration.

Supports PDF, images, and text files with configurable sampling
strategies for handling large documents efficiently.
"""

import asyncio
import mimetypes
from pathlib import Path

from langchain_community.document_loaders import (
    PyPDFLoader,
    TextLoader,
    UnstructuredImageLoader,
)
from langchain_core.documents import Document
from pydantic import BaseModel, Field

from drover.sampling import SampleStrategy


class LoadedDocument(BaseModel):
    """Result of loading a document."""

    path: Path
    content: str = Field(description="Extracted text content")
    page_count: int = Field(default=1, description="Total pages in document")
    pages_sampled: int = Field(default=1, description="Pages actually processed")
    mime_type: str | None = Field(default=None, description="Detected MIME type")

    model_config = {"arbitrary_types_allowed": True}


class DocumentLoadError(Exception):
    """Raised when document loading fails."""

    pass


class DocumentLoader:
    """Loads and samples documents for classification.

    Supports multiple file types and sampling strategies to
    efficiently handle large documents.
    """

    # File extensions to loader class mapping
    _LOADERS: dict[str, type] = {
        ".pdf": PyPDFLoader,
        ".txt": TextLoader,
        ".md": TextLoader,
        ".png": UnstructuredImageLoader,
        ".jpg": UnstructuredImageLoader,
        ".jpeg": UnstructuredImageLoader,
        ".gif": UnstructuredImageLoader,
        ".bmp": UnstructuredImageLoader,
        ".tiff": UnstructuredImageLoader,
        ".tif": UnstructuredImageLoader,
    }

    # Thresholds for adaptive strategy
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

        loader_cls = self._LOADERS.get(suffix)
        if not loader_cls:
            raise DocumentLoadError(f"Unsupported file type: {suffix}")

        try:
            documents = await self._load_with_loader(path, loader_cls)
        except Exception as e:
            raise DocumentLoadError(f"Failed to load {path.name}: {e}") from e

        if not documents:
            raise DocumentLoadError(f"No content extracted from {path.name}")

        # Apply sampling strategy
        total_pages = len(documents)
        sampled_docs = self._apply_sampling(documents, total_pages)

        # Combine content from sampled pages
        content = "\n\n".join(doc.page_content for doc in sampled_docs if doc.page_content.strip())

        if not content.strip():
            raise DocumentLoadError(f"No text content found in {path.name}")

        return LoadedDocument(
            path=path,
            content=content,
            page_count=total_pages,
            pages_sampled=len(sampled_docs),
            mime_type=mime_type,
        )

    async def _load_with_loader(self, path: Path, loader_cls: type) -> list[Document]:
        """Load document using appropriate LangChain loader.

        Args:
            path: Path to document.
            loader_cls: LangChain loader class to use.

        Returns:
            List of Document objects (one per page for PDFs).
        """
        # Most loaders are synchronous, so run them in a thread to avoid
        # blocking the event loop.
        loader = loader_cls(str(path))

        # PyPDFLoader returns one Document per page
        # TextLoader returns one Document for the whole file
        # UnstructuredImageLoader extracts text from images
        return await asyncio.to_thread(loader.load)

    def _apply_sampling(self, documents: list[Document], total_pages: int) -> list[Document]:
        """Apply sampling strategy to document pages.

        Args:
            documents: All loaded document pages.
            total_pages: Total number of pages.

        Returns:
            Sampled subset of documents.
        """
        if total_pages <= self.max_pages:
            return documents

        effective_strategy = self._select_strategy(total_pages)

        match effective_strategy:
            case SampleStrategy.FULL:
                return documents
            case SampleStrategy.FIRST_N:
                return documents[: self.max_pages]
            case SampleStrategy.BOOKENDS:
                half = self.max_pages // 2
                return documents[:half] + documents[-half:]
            case _:
                # Fallback to first_n
                return documents[: self.max_pages]

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

        # Adaptive logic
        if total_pages <= self._SMALL_DOC_PAGES:
            return SampleStrategy.FULL
        elif total_pages <= self._MEDIUM_DOC_PAGES:
            return SampleStrategy.FIRST_N
        else:
            # Large documents: bookends to capture intro and conclusion
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
