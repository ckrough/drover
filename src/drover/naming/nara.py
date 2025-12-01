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

from drover.naming.base import BaseNamingPolicy, NamingConstraints


class NARAPolicyNaming(BaseNamingPolicy):
    """NARA-compliant file naming policy.

    Format: {doctype}-{vendor}-{subject}-{YYYYMMDD}.{ext}

    Examples:
    - statement-chase-checking-20240115.pdf
    - invoice-home_depot-kitchen_faucet-20240220.pdf
    - receipt-amazon-office_supplies-20240301.pdf
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
    ) -> str:
        """Format a NARA-compliant filename.

        Args:
            doctype: Document type (e.g., "statement").
            vendor: Vendor name (e.g., "Chase Bank").
            subject: Subject description (e.g., "checking account").
            date: Date in YYYYMMDD format.
            extension: File extension with dot (e.g., ".pdf").

        Returns:
            Formatted filename like "statement-chase-checking-20240115.pdf".
        """
        sep = self.CONSTRAINTS.component_separator

        # Normalize each component
        norm_doctype = self.normalize_component(doctype)
        norm_vendor = self.normalize_vendor(vendor)
        norm_subject = self.normalize_component(subject)
        norm_date = self._normalize_date(date)

        # Build filename
        components = [norm_doctype, norm_vendor, norm_subject, norm_date]
        base_name = sep.join(c for c in components if c)

        # Ensure extension starts with dot
        if extension and not extension.startswith("."):
            extension = f".{extension}"

        filename = f"{base_name}{extension.lower()}"

        # Validate and truncate if needed
        if len(filename) > self.CONSTRAINTS.max_filename_length:
            # Truncate subject to fit
            max_subject = (
                self.CONSTRAINTS.max_filename_length
                - len(norm_doctype)
                - len(norm_vendor)
                - len(norm_date)
                - len(extension)
                - 3  # Three separators
            )
            if max_subject > 0:
                norm_subject = norm_subject[:max_subject].rstrip(self.CONSTRAINTS.word_separator)
                components = [norm_doctype, norm_vendor, norm_subject, norm_date]
                base_name = sep.join(c for c in components if c)
                filename = f"{base_name}{extension.lower()}"

        return filename

    def _normalize_date(self, date: str) -> str:
        """Normalize date to YYYYMMDD format.

        Accepts various formats and normalizes to 8-digit date.

        Args:
            date: Date string in various formats.

        Returns:
            Date in YYYYMMDD format, or "00000000" if unparseable.
        """
        # Strip non-digits
        digits = "".join(c for c in date if c.isdigit())

        # Already YYYYMMDD
        if len(digits) == 8:
            return digits

        # YYMMDD → YYYYMMDD (assume 2000s)
        if len(digits) == 6:
            return f"20{digits}"

        # YYYY-MM-DD or similar
        if len(digits) >= 8:
            return digits[:8]

        return "00000000"
