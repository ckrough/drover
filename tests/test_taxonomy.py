"""Tests for taxonomy plugin system.

These tests verify the taxonomy plugin MECHANISM, not the specific content
of any particular taxonomy. Taxonomy vocabulary (domains, categories, doctypes)
can change without breaking these tests.
"""

import pytest

from drover.taxonomy import (
    HouseholdTaxonomy,
    get_taxonomy,
    get_taxonomy_loader,
)


class TestHouseholdTaxonomy:
    """Tests for HouseholdTaxonomy plugin mechanism."""

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        """Create taxonomy instance."""
        return HouseholdTaxonomy()

    def test_name(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test taxonomy name."""
        assert taxonomy.name == "household"

    # --- Domain resolution mechanism tests ---

    def test_canonical_domain_case_insensitive(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """Case-insensitive matching works for any valid domain."""
        domains = taxonomy.all_domains()
        if domains:
            sample = domains[0]
            assert taxonomy.canonical_domain(sample.upper()) == sample
            assert taxonomy.canonical_domain(sample.capitalize()) == sample

    def test_canonical_domain_returns_self_for_canonical_values(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """Canonical domains resolve to themselves."""
        for domain in taxonomy.all_domains():
            assert taxonomy.canonical_domain(domain) == domain

    def test_canonical_domain_unknown(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test unknown domain returns None."""
        assert taxonomy.canonical_domain("nonexistent_xyz_123") is None
        assert taxonomy.canonical_domain("random_stuff_456") is None

    # --- Category resolution mechanism tests ---

    def test_canonical_category_returns_self_for_canonical_values(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """Canonical categories resolve to themselves."""
        for domain in taxonomy.all_domains():
            for category in taxonomy.categories_for_domain(domain):
                assert taxonomy.canonical_category(domain, category) == category

    def test_canonical_category_unknown(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test unknown category returns None."""
        # Use a domain we know exists (first one) but with unknown category
        domains = taxonomy.all_domains()
        if domains:
            assert (
                taxonomy.canonical_category(domains[0], "unknown_cat_xyz_789") is None
            )

    # --- Doctype resolution mechanism tests ---

    def test_canonical_doctype_returns_self_for_canonical_values(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """Canonical doctypes resolve to themselves."""
        for doctype in taxonomy.all_doctypes():
            assert taxonomy.canonical_doctype(doctype) == doctype

    def test_canonical_doctype_unknown(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test unknown doctype returns None."""
        assert taxonomy.canonical_doctype("nonexistent_type_xyz_123") is None

    # --- List/enumeration mechanism tests ---

    def test_all_domains_returns_sorted_list(self, taxonomy: HouseholdTaxonomy) -> None:
        """all_domains() returns a sorted, non-empty list."""
        domains = taxonomy.all_domains()
        assert isinstance(domains, list)
        assert domains == sorted(domains)
        assert len(domains) > 0

    def test_categories_for_domain_returns_sorted_list(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """categories_for_domain() returns sorted lists for all domains."""
        for domain in taxonomy.all_domains():
            categories = taxonomy.categories_for_domain(domain)
            assert isinstance(categories, list)
            assert categories == sorted(categories)

    def test_categories_for_unknown_domain(self, taxonomy: HouseholdTaxonomy) -> None:
        """Test categories_for_domain with unknown domain returns empty list."""
        categories = taxonomy.categories_for_domain("nonexistent_domain_xyz")
        assert categories == []

    def test_all_doctypes_returns_sorted_list(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """all_doctypes() returns a sorted, non-empty list."""
        doctypes = taxonomy.all_doctypes()
        assert isinstance(doctypes, list)
        assert doctypes == sorted(doctypes)
        assert len(doctypes) > 0

    def test_to_prompt_menu_returns_string(self, taxonomy: HouseholdTaxonomy) -> None:
        """to_prompt_menu() returns a non-empty string with header."""
        menu = taxonomy.to_prompt_menu()
        assert isinstance(menu, str)
        assert len(menu) > 0
        assert "Valid Classification Options" in menu


class TestHouseholdHierarchyRule:
    """Tests for the household taxonomy's category-vs-doctype hierarchy rule.

    These tests are content-level (not mechanism-level): they assert a specific
    structural invariant of HouseholdTaxonomy — categories name subjects, doctypes
    name forms, and a term cannot be canonical at both layers (with a small
    documented set of straddler exceptions). See docs/taxonomy/proposals.md.
    """

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        return HouseholdTaxonomy()

    def test_no_canonical_category_is_also_canonical_doctype(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        # Round 4: doctypes are plural (LCGFT genre containers) while
        # categories remain singular subject terms. The structural rule still
        # bans semantic collisions, so we normalize both sides through the
        # singular form before comparing — `recipe` (category) and `recipes`
        # (doctype) collide conceptually even when their strings differ.
        def to_singular(value: str) -> str:
            return taxonomy.DOCTYPE_SINGULAR.get(value, value)

        doctype_singulars = {to_singular(d) for d in taxonomy.CANONICAL_DOCTYPES}
        collisions: list[tuple[str, str]] = []
        for domain, categories in taxonomy.CANONICAL_CATEGORIES.items():
            for category in categories:
                if to_singular(category) in doctype_singulars:
                    collisions.append((domain, category))

        # Documented exceptions (deferred straddlers). Each pair stays
        # canonical at both layers because no authority commits cleanly.
        # See docs/taxonomy/proposals.md "Deferred straddlers".
        allowed = {
            # `application` (career): could redirect to `job_search`, but the
            # category captures application-specific workflow distinct from
            # broader job search activity.
            ("career", "application"),
            # `presentation` (career): subject of a presentation varies; no
            # clean replacement category.
            ("career", "presentation"),
        }
        unexpected = [c for c in collisions if c not in allowed]
        assert unexpected == [], (
            f"Canonical categories that are also canonical doctypes: {unexpected}. "
            "Demote them to doctype-only or add to the documented `allowed` set."
        )

    def test_canonical_category_resume_redirects_to_job_search(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        assert taxonomy.canonical_category("career", "resume") == "job_search"

    def test_canonical_category_manual_redirects_to_documentation(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        assert taxonomy.canonical_category("reference", "manual") == "documentation"

    def test_canonical_category_agreement_leaves_gap_in_career(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """No alias for career.agreement — surfaces as drift for ground-truth refinement."""
        assert taxonomy.canonical_category("career", "agreement") is None

    def test_canonical_category_correspondence_demoted_in_personal(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """correspondence is form-only; surfaces as gap in personal domain."""
        assert taxonomy.canonical_category("personal", "correspondence") is None

    def test_canonical_category_correspondence_demoted_in_legal(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        assert taxonomy.canonical_category("legal", "correspondence") is None

    def test_canonical_doctype_correspondence_still_routes_to_letter(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """The doctype alias is unchanged; LLM-emitted 'correspondence' as a doctype still normalizes."""
        assert taxonomy.canonical_doctype("correspondence") == "letters"

    def test_canonical_category_reference_demoted_in_financial(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """reference is form-only; surfaces as gap in financial domain."""
        assert taxonomy.canonical_category("financial", "reference") is None

    def test_canonical_category_reference_demoted_in_medical(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        assert taxonomy.canonical_category("medical", "reference") is None

    def test_canonical_doctype_reference_still_canonical(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """The doctype layer is unchanged; LLM-emitted 'reference' as a doctype still resolves."""
        assert taxonomy.canonical_doctype("reference") == "references"
        assert taxonomy.canonical_doctype("references") == "references"
        assert taxonomy.canonical_doctype("article") == "references"
        assert taxonomy.canonical_doctype("webpage") == "references"


class TestRound4LCGFTAlignment:
    """Round 4: LCGFT plural doctypes, schema.org aliases, demotions."""

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        return HouseholdTaxonomy()

    def test_canonical_doctypes_are_plural(self, taxonomy: HouseholdTaxonomy) -> None:
        for plural in ("receipts", "invoices", "statements", "agreements", "letters"):
            assert plural in taxonomy.CANONICAL_DOCTYPES

    def test_singular_emissions_route_to_plural(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        assert taxonomy.canonical_doctype("receipt") == "receipts"
        assert taxonomy.canonical_doctype("invoice") == "invoices"
        assert taxonomy.canonical_doctype("agreement") == "agreements"

    def test_singular_form_round_trip(self, taxonomy: HouseholdTaxonomy) -> None:
        for plural in taxonomy.CANONICAL_DOCTYPES:
            singular = taxonomy.singular_form(plural)
            assert singular, f"missing singular for {plural}"
            assert taxonomy.canonical_doctype(singular) == plural, (
                f"singular {singular} did not round-trip back to {plural}"
            )

    def test_singular_form_passthrough_for_unknown(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        assert taxonomy.singular_form("nonexistent_xyz") == "nonexistent_xyz"

    def test_contract_doctype_dropped(self, taxonomy: HouseholdTaxonomy) -> None:
        assert "contract" not in taxonomy.CANONICAL_DOCTYPES
        assert "contracts" not in taxonomy.CANONICAL_DOCTYPES
        assert taxonomy.canonical_doctype("contract") == "agreements"
        assert taxonomy.canonical_doctype("contracts") == "agreements"

    def test_legal_contract_category_dropped(self, taxonomy: HouseholdTaxonomy) -> None:
        legal = taxonomy.CANONICAL_CATEGORIES["legal"]
        assert "contract" not in legal
        assert taxonomy.canonical_category("legal", "contract") is None

    def test_food_recipe_category_dropped(self, taxonomy: HouseholdTaxonomy) -> None:
        assert "recipe" not in taxonomy.CANONICAL_CATEGORIES["food"]
        assert taxonomy.canonical_category("food", "recipe") is None

    def test_housing_reservation_category_dropped(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        assert "reservation" not in taxonomy.CANONICAL_CATEGORIES["housing"]
        assert taxonomy.canonical_category("housing", "reservation") is None

    def test_schema_org_reservation_subtypes_alias_to_reservations(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        subtypes = [
            "boat_reservation",
            "bus_reservation",
            "event_reservation",
            "flight_reservation",
            "food_establishment_reservation",
            "lodging_reservation",
            "rental_car_reservation",
            "reservation_package",
            "taxi_reservation",
            "train_reservation",
        ]
        for subtype in subtypes:
            assert taxonomy.canonical_doctype(subtype) == "reservations", subtype

    def test_schema_org_transactional_aliases(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        assert taxonomy.canonical_doctype("order") == "receipts"
        assert taxonomy.canonical_doctype("ticket") == "reservations"
        assert taxonomy.canonical_doctype("tickets") == "reservations"

    def test_authority_gap_fills_present(self, taxonomy: HouseholdTaxonomy) -> None:
        for plural in ("floor_plans", "menus", "maps"):
            assert plural in taxonomy.CANONICAL_DOCTYPES
            assert taxonomy.singular_form(plural)


class TestTaxonomyLoader:
    """Tests for TaxonomyLoader plugin infrastructure."""

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
