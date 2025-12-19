"""Base protocol for metadata extractors.

Extractors are responsible for extracting vendor, date, and subject
from document content. The NLI classifier uses extractors because
NLI models can classify but cannot extract free-form text fields.
"""

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class ExtractionResult:
    """Result of metadata extraction from document content.

    Attributes:
        vendor: Extracted vendor/company name, or "unknown" if not found.
        date: Extracted date in YYYYMMDD format, or "unknown" if not found.
        subject: Extracted subject/description, or "document" if not found.
        confidence: Optional confidence scores for each field (0.0-1.0).
    """

    vendor: str
    date: str
    subject: str
    confidence: dict[str, float] | None = None

    @classmethod
    def unknown(cls) -> "ExtractionResult":
        """Create a result with all unknown values."""
        return cls(vendor="unknown", date="unknown", subject="document")


@runtime_checkable
class BaseExtractor(Protocol):
    """Protocol for metadata extractors.

    Extractors take document content and return structured metadata
    fields (vendor, date, subject) that NLI classifiers cannot extract.

    Implementations may use various approaches:
    - Regex patterns for structured data
    - NER models for entity extraction
    - Small LLMs for semantic extraction
    - Hybrid approaches combining multiple methods
    """

    def extract(self, content: str) -> ExtractionResult:
        """Extract metadata from document content.

        Args:
            content: Full text content of the document.

        Returns:
            ExtractionResult with vendor, date, and subject fields.
        """
        ...
