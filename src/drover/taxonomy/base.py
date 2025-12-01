"""Base taxonomy interface for document classification.

Taxonomies provide a controlled vocabulary for classification, ensuring
consistent and predictable outputs from LLM classification.
"""

from abc import ABC, abstractmethod
from typing import ClassVar


class BaseTaxonomy(ABC):
    """Abstract base class for document taxonomies.

    A taxonomy defines:
    - Canonical domains (top-level categories like "financial", "medical")
    - Canonical categories within each domain
    - Canonical document types
    - Aliases that map variations to canonical values

    Subclasses must define the class variables and may override
    normalization methods for custom logic.
    """

    # Allowed top-level domains
    CANONICAL_DOMAINS: ClassVar[set[str]]

    # Domain → allowed categories mapping
    CANONICAL_CATEGORIES: ClassVar[dict[str, set[str]]]

    # Allowed document types (cross-domain)
    CANONICAL_DOCTYPES: ClassVar[set[str]]

    # Alias mappings: variation → canonical
    DOMAIN_ALIASES: ClassVar[dict[str, str]]

    # Category aliases: (domain, variation) → canonical
    CATEGORY_ALIASES: ClassVar[dict[tuple[str, str], str]]

    # Doctype aliases: variation → canonical
    DOCTYPE_ALIASES: ClassVar[dict[str, str]]

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this taxonomy."""
        ...

    def canonical_domain(self, raw: str) -> str | None:
        """Normalize a raw domain value to its canonical form.

        Args:
            raw: Raw domain string from LLM output.

        Returns:
            Canonical domain string, or None if not recognized.
        """
        normalized = raw.lower().strip().replace(" ", "_")

        # Direct match
        if normalized in self.CANONICAL_DOMAINS:
            return normalized

        # Check aliases
        if normalized in self.DOMAIN_ALIASES:
            return self.DOMAIN_ALIASES[normalized]

        return None

    def canonical_category(self, domain: str, raw: str) -> str | None:
        """Normalize a raw category value within a domain.

        Args:
            domain: The canonical domain this category belongs to.
            raw: Raw category string from LLM output.

        Returns:
            Canonical category string, or None if not recognized.
        """
        normalized = raw.lower().strip().replace(" ", "_")

        # Get valid categories for this domain
        valid_categories = self.CANONICAL_CATEGORIES.get(domain, set())

        # Direct match
        if normalized in valid_categories:
            return normalized

        # Check aliases
        alias_key = (domain, normalized)
        if alias_key in self.CATEGORY_ALIASES:
            return self.CATEGORY_ALIASES[alias_key]

        return None

    def canonical_doctype(self, raw: str) -> str | None:
        """Normalize a raw document type value.

        Args:
            raw: Raw doctype string from LLM output.

        Returns:
            Canonical doctype string, or None if not recognized.
        """
        normalized = raw.lower().strip().replace(" ", "_")

        # Direct match
        if normalized in self.CANONICAL_DOCTYPES:
            return normalized

        # Check aliases
        if normalized in self.DOCTYPE_ALIASES:
            return self.DOCTYPE_ALIASES[normalized]

        return None

    def all_domains(self) -> list[str]:
        """Return sorted list of all canonical domains."""
        return sorted(self.CANONICAL_DOMAINS)

    def categories_for_domain(self, domain: str) -> list[str]:
        """Return sorted list of categories for a domain."""
        return sorted(self.CANONICAL_CATEGORIES.get(domain, set()))

    def all_doctypes(self) -> list[str]:
        """Return sorted list of all canonical doctypes."""
        return sorted(self.CANONICAL_DOCTYPES)

    def to_prompt_menu(self) -> str:
        """Generate a formatted menu of valid options for LLM prompts.

        Returns:
            Markdown-formatted string listing all valid domains,
            categories, and doctypes.
        """
        lines = ["## Valid Classification Options\n"]

        lines.append("### Domains and Categories")
        for domain in self.all_domains():
            lines.append(f"\n**{domain}**:")
            categories = self.categories_for_domain(domain)
            if categories:
                lines.append(f"  - Categories: {', '.join(categories)}")
            else:
                lines.append("  - Categories: (any)")

        lines.append("\n### Document Types")
        lines.append(f"{', '.join(self.all_doctypes())}")

        return "\n".join(lines)
