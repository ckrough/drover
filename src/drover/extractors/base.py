"""Base protocol for metadata extractors.

Extractors are responsible for extracting vendor, date, and subject
from document content. The NLI classifier uses extractors because
NLI models can classify but cannot extract free-form text fields.
"""

from dataclasses import dataclass
from typing import Protocol, TypedDict, runtime_checkable


class StructuredRegion(TypedDict):
    """A typed region from a structure-aware loader (Docling).

    Each region pairs a label (e.g., "Bill To", "Issue Date") with the
    text content of that region. `type` records what kind of region it
    is — "table_row", "key_value", "heading" — so consumers can decide
    whether to interpret the text as a cell value, header, etc.
    """

    type: str
    label: str
    text: str


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

    def extract(
        self,
        content: str,
        structured_regions: list[StructuredRegion] | None = None,
    ) -> ExtractionResult:
        """Extract metadata from document content.

        Args:
            content: Full text content of the document.
            structured_regions: Optional list of typed regions (table cells,
                key-value blocks) derived from a `DoclingDocument`. When
                provided, an extractor should prefer them over flat-text
                regex for fields with matching labels (e.g., "Bill To" for
                vendor, "Issue Date" for date).

        Returns:
            ExtractionResult with vendor, date, and subject fields.
        """
        ...
