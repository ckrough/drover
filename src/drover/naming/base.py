"""Base naming policy interface for file naming conventions.

Naming policies define how classified documents are named, including
character restrictions, format patterns, and length constraints.
"""

import re
from abc import ABC, abstractmethod
from typing import ClassVar

from pydantic import BaseModel, Field


class NamingConstraints(BaseModel):
    """Constraints for generated filenames."""

    max_filename_length: int = Field(default=255, description="Max filename length")
    max_component_length: int = Field(default=50, description="Max length per component")
    allowed_chars_pattern: str = Field(
        default=r"[a-z0-9_-]", description="Regex pattern for allowed chars"
    )
    word_separator: str = Field(default="_", description="Separator between words")
    component_separator: str = Field(default="-", description="Separator between components")


class BaseNamingPolicy(ABC):
    """Abstract base class for file naming policies.

    A naming policy defines:
    - Filename format pattern
    - Character restrictions and normalization
    - Length constraints
    - Component ordering
    """

    CONSTRAINTS: ClassVar[NamingConstraints] = NamingConstraints()

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this naming policy."""
        ...

    @abstractmethod
    def format_filename(
        self,
        doctype: str,
        vendor: str,
        subject: str,
        date: str,
        extension: str,
    ) -> str:
        """Format a filename from classification components.

        Args:
            doctype: Document type (e.g., "statement", "invoice").
            vendor: Vendor/provider name.
            subject: Brief subject description.
            date: Date in YYYYMMDD format.
            extension: File extension including dot (e.g., ".pdf").

        Returns:
            Formatted filename.
        """
        ...

    def normalize_component(self, value: str) -> str:
        """Normalize a single component for use in filename.

        Default implementation:
        - Lowercase
        - Replace spaces/special chars with word separator
        - Strip disallowed characters
        - Truncate to max component length

        Args:
            value: Raw component value.

        Returns:
            Normalized component string.
        """
        constraints = self.CONSTRAINTS

        normalized = value.lower().strip()
        normalized = re.sub(r"\s+", constraints.word_separator, normalized)

        allowed_pattern = constraints.allowed_chars_pattern
        normalized = "".join(
            c for c in normalized if re.match(allowed_pattern, c) or c == constraints.word_separator
        )

        sep = constraints.word_separator
        normalized = re.sub(f"{re.escape(sep)}+", sep, normalized)
        normalized = normalized.strip(sep)

        if len(normalized) > constraints.max_component_length:
            normalized = normalized[: constraints.max_component_length].rstrip(sep)

        return normalized

    def normalize_vendor(self, vendor: str) -> str:
        """Normalize vendor name for filename.

        Override for custom vendor normalization logic.

        Args:
            vendor: Raw vendor name.

        Returns:
            Normalized vendor string.
        """
        vendor = re.sub(r"\b(inc|llc|ltd|corp|co|company)\b\.?", "", vendor, flags=re.IGNORECASE)
        return self.normalize_component(vendor)

    def validate_filename(self, filename: str) -> tuple[bool, str | None]:
        """Validate a generated filename against constraints.

        Args:
            filename: Filename to validate.

        Returns:
            Tuple of (is_valid, error_message).
        """
        constraints = self.CONSTRAINTS

        if len(filename) > constraints.max_filename_length:
            return False, f"Filename exceeds {constraints.max_filename_length} characters"

        base_name = filename.rsplit(".", 1)[0] if "." in filename else filename
        allowed_chars = constraints.allowed_chars_pattern
        if allowed_chars.startswith("[") and allowed_chars.endswith("]"):
            allowed_chars = allowed_chars[1:-1]

        sep = re.escape(constraints.component_separator)
        pattern = f"^[{allowed_chars}{sep}]+$"

        if not re.match(pattern, base_name):
            return False, "Filename contains disallowed characters"

        return True, None
