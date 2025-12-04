"""Taxonomy plugin discovery and loading."""

from drover.taxonomy.base import BaseTaxonomy
from drover.taxonomy.household import HouseholdTaxonomy

_BUILTIN_TAXONOMIES: dict[str, type[BaseTaxonomy]] = {
    "household": HouseholdTaxonomy,
}


class TaxonomyLoader:
    """Discovers and loads taxonomy plugins.

    Built-in taxonomies are always available. User-provided taxonomies
    can be loaded from YAML files or Python modules (future enhancement).
    """

    def __init__(self) -> None:
        """Initialize loader with built-in taxonomies."""
        self._taxonomies: dict[str, BaseTaxonomy] = {}
        self._load_builtins()

    def _load_builtins(self) -> None:
        """Load all built-in taxonomies."""
        for name, taxonomy_cls in _BUILTIN_TAXONOMIES.items():
            self._taxonomies[name] = taxonomy_cls()

    def get(self, name: str) -> BaseTaxonomy | None:
        """Get a taxonomy by name.

        Args:
            name: Taxonomy identifier (e.g., "household").

        Returns:
            Taxonomy instance, or None if not found.
        """
        return self._taxonomies.get(name)

    def list_available(self) -> list[str]:
        """Return list of available taxonomy names."""
        return sorted(self._taxonomies.keys())

    def register(self, taxonomy: BaseTaxonomy) -> None:
        """Register a custom taxonomy.

        Args:
            taxonomy: Taxonomy instance to register.
        """
        self._taxonomies[taxonomy.name] = taxonomy


_loader: TaxonomyLoader | None = None


def get_taxonomy_loader() -> TaxonomyLoader:
    """Get the global taxonomy loader instance."""
    global _loader
    if _loader is None:
        _loader = TaxonomyLoader()
    return _loader


def get_taxonomy(name: str) -> BaseTaxonomy:
    """Get a taxonomy by name.

    Args:
        name: Taxonomy identifier.

    Returns:
        Taxonomy instance.

    Raises:
        ValueError: If taxonomy not found.
    """
    loader = get_taxonomy_loader()
    if taxonomy := loader.get(name):
        return taxonomy
    available = ", ".join(loader.list_available())
    raise ValueError(f"Unknown taxonomy '{name}'. Available: {available}")
