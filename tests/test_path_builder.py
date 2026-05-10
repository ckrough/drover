"""Tests for path builder."""

from pathlib import Path

import pytest

from drover.models import PathConstraints, RawClassification
from drover.naming import NARAPolicyNaming
from drover.path_builder import PathBuilder, PathConstraintError, build_suggested_path
from drover.taxonomy.household import HouseholdTaxonomy


class TestPathBuilder:
    """Tests for PathBuilder."""

    @pytest.fixture
    def policy(self) -> NARAPolicyNaming:
        """Create naming policy."""
        return NARAPolicyNaming()

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        return HouseholdTaxonomy()

    @pytest.fixture
    def builder(
        self, policy: NARAPolicyNaming, taxonomy: HouseholdTaxonomy
    ) -> PathBuilder:
        """Create path builder with taxonomy for plural-folder/singular-filename."""
        return PathBuilder(naming_policy=policy, taxonomy=taxonomy)

    @pytest.fixture
    def classification(self) -> RawClassification:
        """Create sample classification with plural canonical doctype."""
        return RawClassification(
            domain="financial",
            category="banking",
            doctype="statements",
            vendor="Chase Bank",
            date="20240115",
            subject="checking account",
        )

    def test_build_basic(
        self, builder: PathBuilder, classification: RawClassification
    ) -> None:
        original = Path("/documents/scan001.pdf")
        result = builder.build(classification, original)

        assert result.original == "scan001.pdf"
        assert result.domain == "financial"
        assert result.category == "banking"
        assert result.doctype == "statements"
        assert result.suggested_path.startswith("financial/banking/statements/")
        assert result.suggested_path.endswith(".pdf")

    def test_folder_uses_plural_filename_uses_singular(
        self, builder: PathBuilder, classification: RawClassification
    ) -> None:
        original = Path("/documents/test.pdf")
        result = builder.build(classification, original)

        path_parts = result.suggested_path.split("/")
        assert path_parts[0] == "financial"
        assert path_parts[1] == "banking"
        assert path_parts[2] == "statements"
        assert result.suggested_filename.startswith("statement-")

    def test_build_filename_format(
        self, builder: PathBuilder, classification: RawClassification
    ) -> None:
        """Filename starts with the singular instance form (statement)."""
        original = Path("/documents/test.pdf")
        result = builder.build(classification, original)

        filename = result.suggested_path.split("/")[-1]
        parts = filename.replace(".pdf", "").split("-")
        assert parts[0] == "statement"
        assert "chase" in parts[1]
        assert "20240115" in filename

    def test_build_preserves_extension(self, builder: PathBuilder) -> None:
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statements",
            vendor="Chase",
            date="20240115",
            subject="test",
        )
        for ext in [".pdf", ".png", ".jpg", ".txt"]:
            original = Path(f"/documents/test{ext}")
            result = builder.build(classification, original)
            assert result.suggested_path.endswith(ext)

    def test_build_without_taxonomy_passes_doctype_through(
        self, policy: NARAPolicyNaming
    ) -> None:
        """No taxonomy → doctype string is used unchanged for both folder and filename."""
        builder = PathBuilder(naming_policy=policy)
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statements",
            vendor="Chase",
            date="20240115",
            subject="checking",
        )
        original = Path("/documents/test.pdf")
        result = builder.build(classification, original)

        assert "/statements/" in result.suggested_path
        assert result.suggested_filename.startswith("statements-")

    def test_build_with_constraints(
        self, policy: NARAPolicyNaming, taxonomy: HouseholdTaxonomy
    ) -> None:
        constraints = PathConstraints(
            max_path_length=100,
            max_folder_depth=2,
        )
        builder = PathBuilder(
            naming_policy=policy, constraints=constraints, taxonomy=taxonomy
        )
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statements",
            vendor="Test",
            date="20240115",
            subject="test",
        )
        original = Path("/documents/test.pdf")
        result = builder.build(classification, original)

        folder_depth = result.suggested_path.count("/")
        assert folder_depth <= constraints.max_folder_depth

    def test_build_path_length_validation(
        self, policy: NARAPolicyNaming, taxonomy: HouseholdTaxonomy
    ) -> None:
        constraints = PathConstraints(max_path_length=50)
        builder = PathBuilder(
            naming_policy=policy, constraints=constraints, taxonomy=taxonomy
        )
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statements",
            vendor="Very Long Vendor Name That Should Cause Issues",
            date="20240115",
            subject="very long subject description here",
        )
        original = Path("/documents/test.pdf")

        with pytest.raises(PathConstraintError, match="exceeds max length"):
            builder.build(classification, original)

    def test_folder_segments_respect_allowed_chars(
        self, policy: NARAPolicyNaming, taxonomy: HouseholdTaxonomy
    ) -> None:
        constraints = PathConstraints(allowed_chars="0-9")
        builder = PathBuilder(
            naming_policy=policy, constraints=constraints, taxonomy=taxonomy
        )
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statements",
            vendor="Test",
            date="20240115",
            subject="test",
        )
        original = Path("/documents/test.pdf")

        with pytest.raises(PathConstraintError, match="disallowed characters"):
            builder.build(classification, original)


class TestPathBuilderEntity:
    """Tests for the optional entity slot in generated filenames."""

    @pytest.fixture
    def policy(self) -> NARAPolicyNaming:
        return NARAPolicyNaming()

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        return HouseholdTaxonomy()

    @pytest.fixture
    def builder(
        self, policy: NARAPolicyNaming, taxonomy: HouseholdTaxonomy
    ) -> PathBuilder:
        return PathBuilder(naming_policy=policy, taxonomy=taxonomy)

    def test_entity_present_appears_in_filename(self, builder: PathBuilder) -> None:
        classification = RawClassification(
            domain="pets",
            category="medical",
            doctype="invoices",
            vendor="VCA Hospital",
            date="20250416",
            subject="annual checkup",
            entity="Sally",
        )
        result = builder.build(classification, Path("/inbox/scan.pdf"))
        assert result.suggested_filename.endswith(".pdf")
        assert "-sally-" in result.suggested_filename
        assert result.entity == "Sally"

    def test_entity_absent_keeps_four_component_filename(
        self, builder: PathBuilder
    ) -> None:
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statements",
            vendor="Chase Bank",
            date="20240115",
            subject="checking account",
            entity="",
        )
        result = builder.build(classification, Path("/inbox/scan.pdf"))
        # Four components plus extension = three component separators
        stem = result.suggested_filename.rsplit(".", 1)[0]
        assert stem.count("-") == 3

    def test_entity_matching_vendor_is_suppressed(self, builder: PathBuilder) -> None:
        classification = RawClassification(
            domain="lifestyle",
            category="membership",
            doctype="invoices",
            vendor="Trails Offroad",
            date="20250416",
            subject="subscription billing",
            entity="Trails Offroad",
        )
        result = builder.build(classification, Path("/inbox/scan.pdf"))
        assert result.suggested_filename.count("trails_offroad") == 1

    def test_emit_entity_false_suppresses_for_all_documents(
        self, policy: NARAPolicyNaming, taxonomy: HouseholdTaxonomy
    ) -> None:
        builder = PathBuilder(
            naming_policy=policy,
            taxonomy=taxonomy,
            emit_entity=False,
        )
        classification = RawClassification(
            domain="pets",
            category="medical",
            doctype="invoices",
            vendor="VCA Hospital",
            date="20250416",
            subject="annual checkup",
            entity="Sally",
        )
        result = builder.build(classification, Path("/inbox/scan.pdf"))
        assert "sally" not in result.suggested_filename
        # Entity is preserved in the result for downstream consumers (e.g. tags)
        assert result.entity == "Sally"

    def test_redact_entity_for_medical_domain_by_default(
        self, builder: PathBuilder
    ) -> None:
        classification = RawClassification(
            domain="medical",
            category="expense",
            doctype="invoices",
            vendor="Fairfax Medical",
            date="20250416",
            subject="lab work",
            entity="Chris Krough",
        )
        result = builder.build(classification, Path("/inbox/scan.pdf"))
        assert "chris" not in result.suggested_filename.lower()
        assert "krough" not in result.suggested_filename.lower()
        assert result.entity == "Chris Krough"

    def test_redact_list_is_configurable(
        self, policy: NARAPolicyNaming, taxonomy: HouseholdTaxonomy
    ) -> None:
        builder = PathBuilder(
            naming_policy=policy,
            taxonomy=taxonomy,
            redact_entity_in_domains=["pets"],
        )
        classification = RawClassification(
            domain="pets",
            category="medical",
            doctype="invoices",
            vendor="VCA Hospital",
            date="20250416",
            subject="annual checkup",
            entity="Sally",
        )
        result = builder.build(classification, Path("/inbox/scan.pdf"))
        assert "sally" not in result.suggested_filename


class TestEntityMotivatingCases:
    """End-to-end checks for the three motivating cases from prof-fes."""

    @pytest.fixture
    def builder(self) -> PathBuilder:
        return PathBuilder(
            naming_policy=NARAPolicyNaming(),
            taxonomy=HouseholdTaxonomy(),
            # Override the medical-redact default so we can inspect the
            # would-be filename for the medical motivating case below.
            redact_entity_in_domains=[],
        )

    def test_vet_invoice_for_pet(self, builder: PathBuilder) -> None:
        """Pet invoice carries the pet's name in the filename."""
        classification = RawClassification(
            domain="pets",
            category="medical",
            doctype="invoices",
            vendor="VCA Hospital",
            date="20250416",
            subject="annual checkup",
            entity="Sally",
        )
        result = builder.build(classification, Path("/inbox/vet.pdf"))
        assert (
            result.suggested_filename
            == "invoice-vca_hospital-annual_checkup-sally-20250416.pdf"
        )

    def test_medical_bill_with_patient(self, builder: PathBuilder) -> None:
        """Medical bill carries the patient when redaction is disabled."""
        classification = RawClassification(
            domain="medical",
            category="expense",
            doctype="invoices",
            vendor="Fairfax Medical",
            date="20250416",
            subject="lab work",
            entity="C Krough",
        )
        result = builder.build(classification, Path("/inbox/lab.pdf"))
        assert (
            result.suggested_filename
            == "invoice-fairfax_medical-lab_work-c_krough-20250416.pdf"
        )

    def test_concert_reservation_for_performer(self, builder: PathBuilder) -> None:
        """Concert reservation carries the performer's name."""
        classification = RawClassification(
            domain="lifestyle",
            category="entertainment",
            doctype="reservations",
            vendor="Ticketmaster",
            date="20250416",
            subject="concert ticket",
            entity="Taylor Swift",
        )
        result = builder.build(classification, Path("/inbox/ticket.pdf"))
        assert "taylor_swift" in result.suggested_filename
        assert "ticketmaster" in result.suggested_filename
        assert result.suggested_filename.endswith("-20250416.pdf")

    def test_subscription_dedups_with_vendor(self, builder: PathBuilder) -> None:
        """Trails Offroad subscription invoice does not repeat the brand."""
        classification = RawClassification(
            domain="lifestyle",
            category="membership",
            doctype="invoices",
            vendor="Trails Offroad",
            date="20250416",
            subject="subscription billing",
            entity="Trails Offroad",
        )
        result = builder.build(classification, Path("/inbox/sub.pdf"))
        # Vendor and entity match → entity slot is suppressed.
        assert (
            result.suggested_filename
            == "invoice-trails_offroad-subscription_billing-20250416.pdf"
        )


class TestBuildSuggestedPath:
    """Tests for build_suggested_path convenience function."""

    def test_convenience_function(self) -> None:
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statements",
            vendor="Test Bank",
            date="20240115",
            subject="checking",
        )
        policy = NARAPolicyNaming()
        taxonomy = HouseholdTaxonomy()
        original = Path("/documents/test.pdf")

        result = build_suggested_path(
            classification, original, policy, taxonomy=taxonomy
        )

        assert result.original == "test.pdf"
        assert "financial" in result.suggested_path
        assert "/statements/" in result.suggested_path
        assert result.suggested_filename.startswith("statement-")
        assert result.domain == "financial"
