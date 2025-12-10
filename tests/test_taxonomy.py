"""Tests for taxonomy plugin system."""

import pytest

from drover.taxonomy import (
    HouseholdTaxonomy,
    get_taxonomy,
    get_taxonomy_loader,
)


class TestHouseholdTaxonomy:
    """Tests for HouseholdTaxonomy."""

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        """Create taxonomy instance."""
        return HouseholdTaxonomy()

    def test_name(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test taxonomy name."""
        assert taxonomy.name == "household"

    def test_canonical_domain_direct_match(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test direct domain matching."""
        assert taxonomy.canonical_domain("financial") == "financial"
        assert taxonomy.canonical_domain("property") == "property"
        assert taxonomy.canonical_domain("medical") == "medical"
        assert taxonomy.canonical_domain("housing") == "housing"
        assert taxonomy.canonical_domain("career") == "career"
        assert taxonomy.canonical_domain("lifestyle") == "lifestyle"

    def test_canonical_domain_case_insensitive(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test case-insensitive domain matching."""
        assert taxonomy.canonical_domain("Financial") == "financial"
        assert taxonomy.canonical_domain("PROPERTY") == "property"

    def test_canonical_domain_alias(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test domain alias resolution."""
        assert taxonomy.canonical_domain("finances") == "financial"
        assert taxonomy.canonical_domain("money") == "financial"
        assert taxonomy.canonical_domain("home") == "property"
        assert taxonomy.canonical_domain("health") == "medical"
        assert taxonomy.canonical_domain("healthcare") == "medical"
        assert taxonomy.canonical_domain("car") == "vehicles"
        # housing domain aliases
        assert taxonomy.canonical_domain("real_estate") == "housing"
        assert taxonomy.canonical_domain("rental") == "housing"
        assert taxonomy.canonical_domain("apartment") == "housing"

    def test_canonical_domain_unknown(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test unknown domain returns None."""
        assert taxonomy.canonical_domain("nonexistent") is None
        assert taxonomy.canonical_domain("random_stuff") is None

    def test_canonical_category_direct_match(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test direct category matching."""
        assert taxonomy.canonical_category("financial", "banking") == "banking"
        assert taxonomy.canonical_category("financial", "tax") == "tax"
        assert taxonomy.canonical_category("financial", "loan") == "loan"
        assert taxonomy.canonical_category("property", "mortgage") == "mortgage"
        assert taxonomy.canonical_category("property", "improvement") == "improvement"
        assert taxonomy.canonical_category("medical", "primary_care") == "primary_care"
        assert taxonomy.canonical_category("legal", "identification") == "identification"
        assert taxonomy.canonical_category("vehicles", "reference") == "reference"
        assert taxonomy.canonical_category("career", "application") == "application"
        assert taxonomy.canonical_category("food", "recipe") == "recipe"
        assert taxonomy.canonical_category("household", "maintenance") == "maintenance"
        assert taxonomy.canonical_category("lifestyle", "travel") == "travel"
        assert taxonomy.canonical_category("pets", "medical") == "medical"
        assert taxonomy.canonical_category("reference", "manual") == "manual"

    def test_canonical_category_alias(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test category alias resolution."""
        assert taxonomy.canonical_category("financial", "bank") == "banking"
        assert taxonomy.canonical_category("financial", "credit_card") == "credit"
        assert taxonomy.canonical_category("financial", "401k") == "retirement"
        assert taxonomy.canonical_category("property", "repairs") == "maintenance"
        # career domain - "client" is canonical, so it returns directly without alias lookup
        assert taxonomy.canonical_category("career", "client") == "client"
        assert taxonomy.canonical_category("career", "meeting") == "meeting"
        # lifestyle domain aliases
        assert taxonomy.canonical_category("lifestyle", "trip") == "trips"
        assert taxonomy.canonical_category("lifestyle", "vacation") == "trips"
        assert taxonomy.canonical_category("lifestyle", "travel_planning") == "planning"

    def test_canonical_category_unknown(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test unknown category returns None."""
        assert taxonomy.canonical_category("financial", "unknown_cat") is None
        assert taxonomy.canonical_category("property", "random") is None

    def test_canonical_doctype_direct_match(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test direct doctype matching."""
        assert taxonomy.canonical_doctype("statement") == "statement"
        assert taxonomy.canonical_doctype("invoice") == "invoice"
        assert taxonomy.canonical_doctype("receipt") == "receipt"
        assert taxonomy.canonical_doctype("recipe") == "recipe"
        assert taxonomy.canonical_doctype("resume") == "resume"
        assert taxonomy.canonical_doctype("record") == "record"
        assert taxonomy.canonical_doctype("identification") == "identification"

    def test_canonical_doctype_alias(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test doctype alias resolution."""
        assert taxonomy.canonical_doctype("bank_statement") == "statement"
        assert taxonomy.canonical_doctype("rental_agreement") == "lease"
        assert taxonomy.canonical_doctype("cookbook") == "recipe"
        assert taxonomy.canonical_doctype("cv") == "resume"
        assert taxonomy.canonical_doctype("travel_plan") == "itinerary"
        # paystub aliases
        assert taxonomy.canonical_doctype("pay_stub") == "paystub"
        assert taxonomy.canonical_doctype("paycheck") == "paystub"
        # listing and offer aliases
        assert taxonomy.canonical_doctype("property_listing") == "listing"
        assert taxonomy.canonical_doctype("purchase_offer") == "offer"

    def test_canonical_doctype_unknown(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test unknown doctype returns None."""
        assert taxonomy.canonical_doctype("nonexistent_type") is None

    def test_all_domains(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test all_domains returns sorted list."""
        domains = taxonomy.all_domains()
        assert isinstance(domains, list)
        assert domains == sorted(domains)
        assert "financial" in domains
        assert "property" in domains
        assert "housing" in domains
        # All domains
        for domain in [
            "career",
            "food",
            "household",
            "housing",
            "lifestyle",
            "pets",
            "reference",
        ]:
            assert domain in domains

    def test_categories_for_domain(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test categories_for_domain returns sorted list."""
        categories = taxonomy.categories_for_domain("financial")
        assert isinstance(categories, list)
        assert categories == sorted(categories)
        assert "banking" in categories
        assert "tax" in categories
        assert "loan" in categories
        # Spot-check domains
        career_categories = taxonomy.categories_for_domain("career")
        assert "application" in career_categories
        assert "resume" in career_categories
        assert "client" in career_categories
        assert "leadership" in career_categories
        assert "meeting" in career_categories
        assert "documentation" in career_categories
        food_categories = taxonomy.categories_for_domain("food")
        assert "recipe" in food_categories
        household_categories = taxonomy.categories_for_domain("household")
        assert "maintenance" in household_categories
        lifestyle_categories = taxonomy.categories_for_domain("lifestyle")
        assert "travel" in lifestyle_categories
        assert "trips" in lifestyle_categories
        assert "planning" in lifestyle_categories
        pets_categories = taxonomy.categories_for_domain("pets")
        assert "medical" in pets_categories
        # Housing domain
        housing_categories = taxonomy.categories_for_domain("housing")
        assert "property" in housing_categories
        assert "rental" in housing_categories
        assert "search" in housing_categories
        assert "reference" in housing_categories
        # Reference domain
        reference_categories = taxonomy.categories_for_domain("reference")
        assert "manual" in reference_categories
        assert "topic" in reference_categories

    def test_categories_for_unknown_domain(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test categories_for_domain with unknown domain."""
        categories = taxonomy.categories_for_domain("nonexistent")
        assert categories == []

    def test_all_doctypes(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test all_doctypes returns sorted list."""
        doctypes = taxonomy.all_doctypes()
        assert isinstance(doctypes, list)
        assert doctypes == sorted(doctypes)
        assert "statement" in doctypes
        assert "invoice" in doctypes
        # Additional doctypes
        assert "paystub" in doctypes
        assert "lease" in doctypes
        assert "listing" in doctypes
        assert "offer" in doctypes
        assert "receipt" in doctypes
        assert "record" in doctypes

    def test_to_prompt_menu(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test prompt menu generation."""
        menu = taxonomy.to_prompt_menu()
        assert isinstance(menu, str)
        assert "Valid Classification Options" in menu
        assert "financial" in menu
        assert "statement" in menu


class TestTaxonomyLoader:
    """Tests for TaxonomyLoader."""

    def test_get_taxonomy_loader(self) -> None:
        """Test singleton loader."""
        loader1 = get_taxonomy_loader()
        loader2 = get_taxonomy_loader()
        assert loader1 is loader2

    def test_list_available(self) -> None:
        """Test listing available taxonomies."""
        loader = get_taxonomy_loader()
        available = loader.list_available()
        assert "household" in available

    def test_get_taxonomy_success(self) -> None:
        """Test getting taxonomy by name."""
        taxonomy = get_taxonomy("household")
        assert isinstance(taxonomy, HouseholdTaxonomy)

    def test_get_taxonomy_not_found(self) -> None:
        """Test getting nonexistent taxonomy raises error."""
        with pytest.raises(ValueError, match="Unknown taxonomy"):
            get_taxonomy("nonexistent")
