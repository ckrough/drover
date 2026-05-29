"""NARA-compliant naming policy.

Based on National Archives and Records Administration (NARA) file naming
conventions for electronic records. Emphasizes:
- Lowercase alphanumeric characters
- Underscores for word separation within components
- Hyphens for component separation
- Date at end in YYYYMMDD format
- Meaningful, descriptive names
"""

from typing import ClassVar

from drover.dates import normalize_classification_date
from drover.naming.base import BaseNamingPolicy, NamingConstraints


class NARAPolicyNaming(BaseNamingPolicy):
    """NARA-compliant file naming policy.

    Format: {doctype}-{vendor}-{subject}-{entity}-{YYYYMMDD}.{ext}

    The entity slot is optional and is dropped when empty or when its
    normalized form matches the normalized vendor (so the same name
    is not repeated in two adjacent slots).

    Examples:
    - statement-chase-checking-20240115.pdf
    - invoice-home_depot-kitchen_faucet-20240220.pdf
    - receipt-amazon-office_supplies-20240301.pdf
    - invoice-vca_hospital-annual_checkup-sally-20250416.pdf
    """

    CONSTRAINTS: ClassVar[NamingConstraints] = NamingConstraints(
        max_filename_length=255,
        max_component_length=40,
        allowed_chars_pattern=r"[a-z0-9_]",
        word_separator="_",
        component_separator="-",
    )

    @property
    def name(self) -> str:
        """Unique identifier for this naming policy."""
        return "nara"

    def format_filename(
        self,
        doctype: str,
        vendor: str,
        subject: str,
        date: str,
        extension: str,
        entity: str = "",
    ) -> str:
        """Format a NARA-compliant filename.

        Args:
            doctype: Document type (e.g., "statement").
            vendor: Vendor name (e.g., "Chase Bank").
            subject: Subject description (e.g., "checking account").
            date: Date in YYYYMMDD format.
            extension: File extension with dot (e.g., ".pdf").
            entity: Optional principal named entity. Suppressed when empty
                or when its normalized form equals the normalized vendor.

        Returns:
            Formatted filename like "statement-chase-checking-20240115.pdf"
            or "invoice-vca-checkup-sally-20250416.pdf" when entity is set.
        """
        sep = self.CONSTRAINTS.component_separator

        norm_doctype = self.normalize_component(doctype)
        norm_vendor = self.normalize_vendor(vendor)
        norm_subject = self.normalize_component(subject)
        norm_entity = self.normalize_component(entity) if entity else ""
        if norm_entity and norm_entity == norm_vendor:
            norm_entity = ""
        norm_date = self._normalize_date(date)

        components = [
            norm_doctype,
            norm_vendor,
            norm_subject,
            norm_entity,
            norm_date,
        ]
        base_name = sep.join(c for c in components if c)

        if extension and not extension.startswith("."):
            extension = f".{extension}"

        filename = f"{base_name}{extension.lower()}"

        if len(filename) > self.CONSTRAINTS.max_filename_length:
            present_separators = (
                sum(1 for c in components if c) - 1
            )  # one fewer separator than components
            max_subject = (
                self.CONSTRAINTS.max_filename_length
                - len(norm_doctype)
                - len(norm_vendor)
                - len(norm_entity)
                - len(norm_date)
                - len(extension)
                - max(present_separators, 0)
            )
            if max_subject > 0:
                norm_subject = norm_subject[:max_subject].rstrip(
                    self.CONSTRAINTS.word_separator
                )
                components = [
                    norm_doctype,
                    norm_vendor,
                    norm_subject,
                    norm_entity,
                    norm_date,
                ]
                base_name = sep.join(c for c in components if c)
                filename = f"{base_name}{extension.lower()}"

        return filename

    def _normalize_date(self, date: str | None) -> str:
        """Normalize a date string to YYYYMMDD format.

        Delegates to :func:`drover.dates.normalize_classification_date`,
        which strips non-ASCII-digit characters, expands 6-digit
        ``YYMMDD`` inputs, and returns the ``"00000000"`` sentinel for
        any partial-zero, impossible, or otherwise invalid date.

        Args:
            date: Date string in various formats, or ``None``.

        Returns:
            A real YYYYMMDD date, or ``"00000000"`` if unparseable or invalid.
        """
        return normalize_classification_date(date)
