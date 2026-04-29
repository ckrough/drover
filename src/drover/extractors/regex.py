"""Regex-based metadata extractor.

Extracts vendor, date, and subject from document content using
regular expression patterns. This is a lightweight approach that
works well for structured documents with predictable formats.
"""

import re
from calendar import month_abbr, month_name
from dataclasses import dataclass, field

from drover.extractors.base import BaseExtractor, ExtractionResult, StructuredRegion

_VENDOR_LABEL_KEYWORDS = ("bill to", "vendor", "from", "supplier", "company")
_DATE_LABEL_KEYWORDS = (
    "date",
    "issue date",
    "statement date",
    "invoice date",
    "billing date",
    "due date",
)


@dataclass
class RegexExtractor:
    """Extract metadata using regex patterns.

    Patterns are designed for common document formats:
    - Dates: ISO format, US format, written format
    - Vendors: Letterheads, sender lines, company suffixes
    - Subject: First meaningful line or document title

    Attributes:
        max_vendor_length: Maximum length for extracted vendor names.
        max_subject_length: Maximum length for extracted subjects.
        search_window: Number of characters to search for vendor/date.
    """

    max_vendor_length: int = 50
    max_subject_length: int = 100
    search_window: int = 2000

    # Date patterns - order matters (more specific first)
    _date_patterns: list[tuple[str, str]] = field(
        default_factory=lambda: [
            # ISO format: 2024-01-15, 2024/01/15
            (r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", "ymd"),
            # US format: 01/15/2024, 01-15-2024
            (r"\b(\d{1,2})[-/](\d{1,2})[-/](\d{4})\b", "mdy"),
            # Written: January 15, 2024 or Jan 15, 2024
            (
                r"\b((?:{})\w*)\s+(\d{{1,2}}),?\s+(\d{{4}})\b".format(
                    "|".join(m for m in list(month_name)[1:] + list(month_abbr)[1:])
                ),
                "Mdy",
            ),
            # Written: 15 January 2024
            (
                r"\b(\d{{1,2}})\s+((?:{})\w*)\s+(\d{{4}})\b".format(
                    "|".join(m for m in list(month_name)[1:] + list(month_abbr)[1:])
                ),
                "dMy",
            ),
        ]
    )

    # Company suffixes to identify vendor names
    _company_suffixes: tuple[str, ...] = (
        r"Inc\.?",
        r"LLC",
        r"Corp\.?",
        r"Corporation",
        r"Ltd\.?",
        r"Limited",
        r"Co\.?",
        r"Company",
        r"Group",
        r"Holdings",
        r"Services",
        r"Solutions",
        r"Partners",
        r"Associates",
        r"Bank",
        r"Insurance",
        r"Financial",
        r"Credit Union",
    )

    # Patterns that indicate vendor/sender information.
    # Each entry below is a regex; the surrounding comments label what kind
    # of construct the next pattern matches.
    _vendor_patterns: list[str] = field(
        default_factory=lambda: [
            # Match a company name with corporate suffix at start of document
            r"^([A-Z][A-Za-z\s&.,]+(?:Inc\.?|LLC|Corp\.?|Ltd\.?|Company|Bank))",
            # Match a From header
            r"From:\s*([A-Za-z][A-Za-z\s&.,]+)",
            # Match a Sender header
            r"Sender:\s*([A-Za-z][A-Za-z\s&.,]+)",
            # Match an "Account with/at" phrase
            r"Account\s+(?:with|at):\s*([A-Za-z][A-Za-z\s&.,]+)",
            # Match a "Statement from" phrase
            r"Statement\s+from\s+([A-Za-z][A-Za-z\s&.,]+)",
            # Match a "Bill from" or "Invoice from" phrase
            r"(?:Bill|Invoice)\s+from\s+([A-Za-z][A-Za-z\s&.,]+)",
        ]
    )

    def extract(
        self,
        content: str,
        structured_regions: list[StructuredRegion] | None = None,
    ) -> ExtractionResult:
        """Extract vendor, date, and subject from content.

        Args:
            content: Document text content.
            structured_regions: Optional typed regions (e.g., table rows)
                from a structure-aware loader. Vendor and date lookups
                prefer them over flat-text regex when a region's label
                matches a known keyword.

        Returns:
            ExtractionResult with extracted or default values.
        """
        # Use search window for vendor/date (usually in header)
        header = content[: self.search_window]

        vendor = self._lookup_region(structured_regions, _VENDOR_LABEL_KEYWORDS)
        if vendor is None:
            vendor = self._extract_vendor(header)
        else:
            vendor = self._truncate_vendor(vendor)

        date_from_region = self._lookup_region(structured_regions, _DATE_LABEL_KEYWORDS)
        if date_from_region is not None:
            normalized = self._extract_date(date_from_region)
            date = (
                normalized if normalized != "unknown" else self._extract_date(content)
            )
        else:
            date = self._extract_date(content)

        subject = self._extract_subject(content)

        return ExtractionResult(
            vendor=vendor,
            date=date,
            subject=subject,
        )

    @staticmethod
    def _lookup_region(
        regions: list[StructuredRegion] | None, label_keywords: tuple[str, ...]
    ) -> str | None:
        """Return the first region text whose label matches a keyword.

        Match is case-insensitive substring; the *first* match wins because
        document-order tables put primary fields before secondary ones.
        """
        if not regions:
            return None
        for region in regions:
            label = region["label"].strip().lower()
            for kw in label_keywords:
                if kw in label:
                    text = region["text"].strip()
                    if text:
                        return text
        return None

    def _truncate_vendor(self, vendor: str) -> str:
        """Trim vendor text to the configured max length without splitting words."""
        vendor = re.sub(r"[.,]+$", "", vendor.strip())
        if len(vendor) > self.max_vendor_length:
            vendor = vendor[: self.max_vendor_length].rsplit(" ", 1)[0]
        return vendor

    def _extract_date(self, content: str) -> str:
        """Extract and normalize date to YYYYMMDD format."""
        for pattern, fmt in self._date_patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                try:
                    return self._normalize_date(match.groups(), fmt)
                except ValueError:
                    continue
        return "unknown"

    def _normalize_date(self, groups: tuple[str, ...], fmt: str) -> str:
        """Convert matched date groups to YYYYMMDD format.

        Args:
            groups: Regex match groups.
            fmt: Format indicator (ymd, mdy, Mdy, dMy).

        Returns:
            Date string in YYYYMMDD format.

        Raises:
            ValueError: If date components are invalid.
        """
        if fmt == "ymd":
            year, month, day = groups
        elif fmt == "mdy":
            month, day, year = groups
        elif fmt == "Mdy":
            month_str, day, year = groups
            month = str(self._month_to_number(month_str))
        elif fmt == "dMy":
            day, month_str, year = groups
            month = str(self._month_to_number(month_str))
        else:
            raise ValueError(f"Unknown date format: {fmt}")

        # Validate and normalize
        year_int = int(year)
        month_int = int(month)
        day_int = int(day)

        if not (1 <= month_int <= 12):
            raise ValueError(f"Invalid month: {month_int}")
        if not (1 <= day_int <= 31):
            raise ValueError(f"Invalid day: {day_int}")
        if not (1900 <= year_int <= 2100):
            raise ValueError(f"Invalid year: {year_int}")

        return f"{year_int:04d}{month_int:02d}{day_int:02d}"

    def _month_to_number(self, month_str: str) -> int:
        """Convert month name/abbreviation to number.

        Args:
            month_str: Month name like "January" or "Jan".

        Returns:
            Month number (1-12).

        Raises:
            ValueError: If month name not recognized.
        """
        month_lower = month_str.lower()[:3]
        month_map = {m.lower()[:3]: i for i, m in enumerate(month_name) if m}
        month_map.update({m.lower()[:3]: i for i, m in enumerate(month_abbr) if m})

        if month_lower in month_map:
            return month_map[month_lower]
        raise ValueError(f"Unknown month: {month_str}")

    def _extract_vendor(self, content: str) -> str:
        """Extract vendor name from document header."""
        for pattern in self._vendor_patterns:
            match = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
            if match:
                vendor = match.group(1).strip()
                # Clean up trailing punctuation
                vendor = re.sub(r"[.,]+$", "", vendor)
                # Truncate if too long
                if len(vendor) > self.max_vendor_length:
                    vendor = vendor[: self.max_vendor_length].rsplit(" ", 1)[0]
                return vendor

        # Fallback: look for company suffix pattern anywhere
        suffix_pattern = r"([A-Z][A-Za-z\s&]+(?:{}))\b".format(
            "|".join(self._company_suffixes)
        )
        match = re.search(suffix_pattern, content)
        if match:
            vendor = match.group(1).strip()
            if len(vendor) > self.max_vendor_length:
                vendor = vendor[: self.max_vendor_length].rsplit(" ", 1)[0]
            return vendor

        return "unknown"

    def _extract_subject(self, content: str) -> str:
        """Extract subject from document content.

        Looks for the first meaningful line that could serve as a title
        or subject description.
        """
        lines = content.strip().split("\n")

        for line in lines[:20]:  # Check first 20 lines
            cleaned = line.strip()

            # Skip empty lines
            if not cleaned:
                continue

            # Skip very short lines (likely headers/labels)
            if len(cleaned) < 10:
                continue

            # Skip lines that are all caps (likely headers)
            if cleaned.isupper() and len(cleaned) < 50:
                continue

            # Skip lines that look like addresses or dates
            if re.match(r"^\d+\s+[A-Z]", cleaned):  # Address
                continue
            if re.match(r"^(?:Date|To|From|Re|Subject):", cleaned, re.IGNORECASE):
                continue

            # Found a good candidate
            subject = cleaned
            if len(subject) > self.max_subject_length:
                subject = subject[: self.max_subject_length].rsplit(" ", 1)[0] + "..."
            return subject

        return "document"


# Ensure RegexExtractor implements BaseExtractor protocol
assert isinstance(RegexExtractor(), BaseExtractor)
