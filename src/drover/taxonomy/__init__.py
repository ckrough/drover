"""Taxonomy plugin system for consistent document classification."""

from drover.taxonomy.base import BaseTaxonomy
from drover.taxonomy.household import HouseholdTaxonomy
from drover.taxonomy.loader import TaxonomyLoader, get_taxonomy, get_taxonomy_loader

__all__ = [
    "BaseTaxonomy",
    "HouseholdTaxonomy",
    "TaxonomyLoader",
    "get_taxonomy",
    "get_taxonomy_loader",
]
