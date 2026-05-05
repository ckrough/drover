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

    CANONICAL_DOMAINS: ClassVar[set[str]]
    CANONICAL_CATEGORIES: ClassVar[dict[str, set[str]]]
    CANONICAL_DOCTYPES: ClassVar[set[str]]
    DOMAIN_ALIASES: ClassVar[dict[str, str]]
    CATEGORY_ALIASES: ClassVar[dict[tuple[str, str], str]]
    DOCTYPE_ALIASES: ClassVar[dict[str, str]]
    DOCTYPE_SINGULAR: ClassVar[dict[str, str]] = {}

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

        if normalized in self.CANONICAL_DOMAINS:
            return normalized

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
        valid_categories = self.CANONICAL_CATEGORIES.get(domain, set())

        if normalized in valid_categories:
            return normalized

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

        if normalized in self.CANONICAL_DOCTYPES:
            return normalized

        if normalized in self.DOCTYPE_ALIASES:
            return self.DOCTYPE_ALIASES[normalized]

        return None

    def singular_form(self, doctype: str) -> str:
        """Return the singular instance form of a (plural) canonical doctype.

        Folders use plural canonical doctypes (LCGFT genre alignment); filenames
        use the singular form (one file = one instance). Falls back to the input
        when no mapping exists, so callers can pass any string safely.
        """
        return self.DOCTYPE_SINGULAR.get(doctype, doctype)

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
