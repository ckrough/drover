"""Tests for path builder."""

from pathlib import Path

import pytest

from drover.models import PathConstraints, RawClassification
from drover.naming import NARAPolicyNaming
from drover.path_builder import PathBuilder, build_suggested_path


class TestPathBuilder:
    """Tests for PathBuilder."""

    @pytest.fixture
    def policy(self) -> NARAPolicyNaming:
        """Create naming policy."""
        return NARAPolicyNaming()

    @pytest.fixture
    def builder(self, policy: NARAPolicyNaming) -> PathBuilder:
        """Create path builder."""
        return PathBuilder(naming_policy=policy)

    @pytest.fixture
    def classification(self) -> RawClassification:
        """Create sample classification."""
        return RawClassification(
            domain="financial",
            category="banking",
            doctype="statement",
            vendor="Chase Bank",
            date="20240115",
            subject="checking account",
        )

    def test_build_basic(self, builder: PathBuilder, classification: RawClassification) -> None:
        """Test basic path building."""
        original = Path("/documents/scan001.pdf")
        result = builder.build(classification, original)

        assert result.original == "scan001.pdf"
        assert result.domain == "financial"
        assert result.category == "banking"
        assert result.doctype == "statement"
        assert result.suggested_path.startswith("financial/banking/statement/")
        assert result.suggested_path.endswith(".pdf")

    def test_build_folder_structure(
        self, builder: PathBuilder, classification: RawClassification
    ) -> None:
        """Test correct folder structure."""
        original = Path("/documents/test.pdf")
        result = builder.build(classification, original)

        path_parts = result.suggested_path.split("/")
        assert path_parts[0] == "financial"
        assert path_parts[1] == "banking"
        assert path_parts[2] == "statement"

    def test_build_filename_format(
        self, builder: PathBuilder, classification: RawClassification
    ) -> None:
        """Test filename follows NARA format."""
        original = Path("/documents/test.pdf")
        result = builder.build(classification, original)

        filename = result.suggested_path.split("/")[-1]
        # Format: doctype-vendor-subject-date.ext
        parts = filename.replace(".pdf", "").split("-")
        assert parts[0] == "statement"  # doctype
        assert "chase" in parts[1]  # vendor
        assert "20240115" in filename  # date

    def test_build_preserves_extension(self, builder: PathBuilder) -> None:
        """Test original file extension is preserved."""
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statement",
            vendor="Chase",
            date="20240115",
            subject="test",
        )

        # Test various extensions
        for ext in [".pdf", ".png", ".jpg", ".txt"]:
            original = Path(f"/documents/test{ext}")
            result = builder.build(classification, original)
            assert result.suggested_path.endswith(ext)

    def test_build_with_constraints(self, policy: NARAPolicyNaming) -> None:
        """Test path building with custom constraints."""
        constraints = PathConstraints(
            max_path_length=100,
            max_folder_depth=2,
        )
        builder = PathBuilder(naming_policy=policy, constraints=constraints)

        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statement",
            vendor="Test",
            date="20240115",
            subject="test",
        )
        original = Path("/documents/test.pdf")
        result = builder.build(classification, original)

        # Folder depth should be limited to 2
        folder_depth = result.suggested_path.count("/")
        assert folder_depth <= constraints.max_folder_depth

    def test_build_path_length_validation(self, policy: NARAPolicyNaming) -> None:
        """Test path length constraint validation."""
        constraints = PathConstraints(max_path_length=50)
        builder = PathBuilder(naming_policy=policy, constraints=constraints)

        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statement",
            vendor="Very Long Vendor Name That Should Cause Issues",
            date="20240115",
            subject="very long subject description here",
        )
        original = Path("/documents/test.pdf")

        # Should raise due to path length
        with pytest.raises(ValueError, match="exceeds max length"):
            builder.build(classification, original)


class TestBuildSuggestedPath:
    """Tests for build_suggested_path convenience function."""

    def test_convenience_function(self) -> None:
        """Test convenience function works."""
        classification = RawClassification(
            domain="financial",
            category="banking",
            doctype="statement",
            vendor="Test Bank",
            date="20240115",
            subject="checking",
        )
        policy = NARAPolicyNaming()
        original = Path("/documents/test.pdf")

        result = build_suggested_path(classification, original, policy)

        assert result.original == "test.pdf"
        assert "financial" in result.suggested_path
        assert result.domain == "financial"
