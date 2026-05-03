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
        doctype_set = taxonomy.CANONICAL_DOCTYPES
        collisions: list[tuple[str, str]] = []
        for domain, categories in taxonomy.CANONICAL_CATEGORIES.items():
            for category in categories:
                if category in doctype_set:
                    collisions.append((domain, category))
        # Documented exceptions (deferred refactors). Each pair stays canonical
        # at both layers because the demotion has no clean replacement category
        # or because the term carries genuine subject meaning in that domain.
        # See docs/taxonomy/proposals.md "Deferred straddlers".
        allowed = {
            # `contract` (legal): no clean replacement; a legal contract's
            # subject is often the contract itself.
            ("legal", "contract"),
            # `application` (career): could redirect to `job_search`, but the
            # category captures application-specific workflow (offers, follow-ups)
            # distinct from broader job search activity.
            ("career", "application"),
            # `presentation` (career): subject of a presentation varies; no clean
            # replacement category.
            ("career", "presentation"),
            # `recipe` (food): the subject of a recipe document is the recipe
            # itself; category and form genuinely coincide here.
            ("food", "recipe"),
            # `reservation` (housing): could redirect to `rental` for short-term
            # bookings, but reservation carries timing/availability semantics
            # that `rental` doesn't.
            ("housing", "reservation"),
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
        assert taxonomy.canonical_doctype("correspondence") == "letter"

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
        assert taxonomy.canonical_doctype("reference") == "reference"
        assert taxonomy.canonical_doctype("article") == "reference"
        assert taxonomy.canonical_doctype("webpage") == "reference"


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
