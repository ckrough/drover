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
