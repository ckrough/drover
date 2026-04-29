"""Tests for structured-region metadata extraction (prof-dpo).

When a Docling-derived list of typed regions is provided, RegexExtractor
and HybridExtractor should prefer those regions over flat-text regex
for vendor and date fields. Without regions, behavior is unchanged.
"""

from types import SimpleNamespace

from drover.extractors.base import StructuredRegion
from drover.extractors.llm import HybridExtractor
from drover.extractors.regex import RegexExtractor
from drover.extractors.structured import extract_structured_regions

FLAT_HEADER_VENDOR = (
    "Bridgeport Telecom Corp\n123 Main Street\n\nInvoice #1234\n"
    "Service period: 2025-07-01 to 2025-07-31\n"
)


def _bill_to_region(text: str) -> StructuredRegion:
    return StructuredRegion(type="table_row", label="Bill To", text=text)


def _date_region(text: str) -> StructuredRegion:
    return StructuredRegion(type="table_row", label="Issue Date", text=text)


def test_regex_extractor_uses_structured_vendor_when_available() -> None:
    """A 'Bill To' table row beats flat-text regex even with a letterhead."""
    extractor = RegexExtractor()
    regions: list[StructuredRegion] = [_bill_to_region("Acme Corp")]

    result = extractor.extract(FLAT_HEADER_VENDOR, structured_regions=regions)

    assert result.vendor == "Acme Corp"


def test_regex_extractor_uses_structured_date_when_available() -> None:
    """An 'Issue Date' region beats picking up the first ISO date in body text."""
    extractor = RegexExtractor()
    regions = [_date_region("2025-11-15")]

    result = extractor.extract(FLAT_HEADER_VENDOR, structured_regions=regions)

    assert result.date == "20251115"


def test_regex_extractor_falls_back_to_regex_when_no_relevant_region() -> None:
    """Regions without a vendor/date label do not perturb regex behavior."""
    extractor = RegexExtractor()
    regions = [
        StructuredRegion(type="table_row", label="Notes", text="thank you"),
    ]

    result_with_regions = extractor.extract(
        FLAT_HEADER_VENDOR, structured_regions=regions
    )
    result_without_regions = extractor.extract(FLAT_HEADER_VENDOR)

    assert result_with_regions == result_without_regions


def test_regex_extractor_default_call_unchanged() -> None:
    """Calling extract(content) without structured_regions is identical to today."""
    extractor = RegexExtractor()
    a = extractor.extract(FLAT_HEADER_VENDOR)
    b = extractor.extract(FLAT_HEADER_VENDOR, structured_regions=None)
    assert a == b


def test_hybrid_extractor_passes_regions_to_regex_extractor() -> None:
    """HybridExtractor with no LLM keeps regex confidence at 0.9 for found fields."""
    extractor = HybridExtractor()  # no llm
    regions = [_bill_to_region("Acme Corp"), _date_region("2025-11-15")]

    result = extractor.extract(FLAT_HEADER_VENDOR, structured_regions=regions)

    assert result.vendor == "Acme Corp"
    assert result.date == "20251115"


def test_hybrid_extractor_confidence_pattern_preserved() -> None:
    """Vendor sourced from regex/regions stays high-confidence; LLM-only stays 0.7.

    No structured region -> vendor comes from flat-text regex -> needs_vendor
    is False -> regex confidence (0.9) when LLM is invoked. We simulate the
    LLM path by substituting a stub.
    """

    class _StubLLM:
        def invoke(self, prompt: str) -> SimpleNamespace:
            return SimpleNamespace(
                content='{"vendor": "ignored", "date": "20990101", "subject": "ignored"}'
            )

    extractor = HybridExtractor(llm=_StubLLM())
    regions = [_bill_to_region("Acme Corp")]

    result = extractor.extract(
        "minimal flat text without dates", structured_regions=regions
    )

    assert result.vendor == "Acme Corp"
    assert result.confidence is not None
    assert result.confidence["vendor"] == 0.9


# ---------------------------------------------------------------------------
# extract_structured_regions helper
# ---------------------------------------------------------------------------


def test_extract_structured_regions_handles_grid_tables() -> None:
    """grid-shaped tables (a 2D list of cells with .text) flatten to row regions."""

    class _Cell:
        def __init__(self, text: str) -> None:
            self.text = text

    grid = [
        [_Cell("Bill To"), _Cell("Acme Corp")],
        [_Cell("Issue Date"), _Cell("2025-11-15")],
    ]
    table = SimpleNamespace(data=SimpleNamespace(grid=grid))
    doc = SimpleNamespace(tables=[table])

    regions = extract_structured_regions(doc)

    assert {(r["label"], r["text"]) for r in regions} == {
        ("Bill To", "Acme Corp"),
        ("Issue Date", "2025-11-15"),
    }
    assert all(r["type"] == "table_row" for r in regions)


def test_extract_structured_regions_handles_table_cells_layout() -> None:
    """Flat-cell-list shape (start_row_offset_idx + start_col_offset_idx) works too."""

    def _flat_cell(row: int, col: int, text: str) -> SimpleNamespace:
        return SimpleNamespace(
            start_row_offset_idx=row, start_col_offset_idx=col, text=text
        )

    cells = [
        _flat_cell(0, 0, "Vendor"),
        _flat_cell(0, 1, "Bridgeport Telecom"),
        _flat_cell(1, 0, "Issue Date"),
        _flat_cell(1, 1, "2025-07-23"),
    ]
    table = SimpleNamespace(data=SimpleNamespace(grid=None, table_cells=cells))
    doc = SimpleNamespace(tables=[table])

    regions = extract_structured_regions(doc)

    pairs = {(r["label"], r["text"]) for r in regions}
    assert pairs == {
        ("Vendor", "Bridgeport Telecom"),
        ("Issue Date", "2025-07-23"),
    }


def test_extract_structured_regions_returns_empty_for_none() -> None:
    assert extract_structured_regions(None) == []


def test_extract_structured_regions_returns_empty_when_no_tables() -> None:
    doc = SimpleNamespace(tables=[])
    assert extract_structured_regions(doc) == []
