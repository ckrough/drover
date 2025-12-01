"""Tests for naming policy system."""

import pytest

from drover.naming import (
    NARAPolicyNaming,
    get_naming_loader,
    get_naming_policy,
)


class TestNARAPolicyNaming:
    """Tests for NARA naming policy."""

    @pytest.fixture
    def policy(self) -> NARAPolicyNaming:
        """Create policy instance."""
        return NARAPolicyNaming()

    def test_name(self, policy: NARAPolicyNaming) -> None:
        """Test policy name."""
        assert policy.name == "nara"

    def test_format_filename_basic(self, policy: NARAPolicyNaming) -> None:
        """Test basic filename formatting."""
        filename = policy.format_filename(
            doctype="statement",
            vendor="Chase",
            subject="checking account",
            date="20240115",
            extension=".pdf",
        )
        assert filename == "statement-chase-checking_account-20240115.pdf"

    def test_format_filename_normalizes_vendor(self, policy: NARAPolicyNaming) -> None:
        """Test vendor name normalization."""
        filename = policy.format_filename(
            doctype="invoice",
            vendor="Home Depot Inc.",
            subject="kitchen faucet",
            date="20240220",
            extension=".pdf",
        )
        # Inc. should be stripped
        assert "inc" not in filename.lower()
        assert "home_depot" in filename

    def test_format_filename_normalizes_subject(self, policy: NARAPolicyNaming) -> None:
        """Test subject normalization with spaces."""
        filename = policy.format_filename(
            doctype="receipt",
            vendor="Amazon",
            subject="office supplies",
            date="20240301",
            extension=".pdf",
        )
        assert "office_supplies" in filename

    def test_format_filename_lowercase(self, policy: NARAPolicyNaming) -> None:
        """Test filename is all lowercase."""
        filename = policy.format_filename(
            doctype="STATEMENT",
            vendor="CHASE BANK",
            subject="CHECKING",
            date="20240115",
            extension=".PDF",
        )
        assert filename == filename.lower()

    def test_format_filename_date_normalization(self, policy: NARAPolicyNaming) -> None:
        """Test various date format normalizations."""
        # Already YYYYMMDD
        filename = policy.format_filename(
            doctype="statement",
            vendor="test",
            subject="test",
            date="20240115",
            extension=".pdf",
        )
        assert "20240115" in filename

        # YYMMDD -> 20YYMMDD
        filename = policy.format_filename(
            doctype="statement",
            vendor="test",
            subject="test",
            date="240115",
            extension=".pdf",
        )
        assert "20240115" in filename

    def test_format_filename_missing_extension_dot(self, policy: NARAPolicyNaming) -> None:
        """Test extension without leading dot."""
        filename = policy.format_filename(
            doctype="statement",
            vendor="test",
            subject="test",
            date="20240115",
            extension="pdf",
        )
        assert filename.endswith(".pdf")

    def test_normalize_component_basic(self, policy: NARAPolicyNaming) -> None:
        """Test basic component normalization."""
        assert policy.normalize_component("Hello World") == "hello_world"
        assert policy.normalize_component("test") == "test"

    def test_normalize_component_special_chars(self, policy: NARAPolicyNaming) -> None:
        """Test special character removal."""
        result = policy.normalize_component("Test@#$%Value")
        assert "@" not in result
        assert "#" not in result

    def test_normalize_component_truncation(self, policy: NARAPolicyNaming) -> None:
        """Test long component truncation."""
        long_value = "a" * 100
        result = policy.normalize_component(long_value)
        assert len(result) <= policy.CONSTRAINTS.max_component_length

    def test_normalize_vendor_removes_suffix(self, policy: NARAPolicyNaming) -> None:
        """Test vendor suffix removal."""
        assert policy.normalize_vendor("Acme Inc.") == "acme"
        assert policy.normalize_vendor("Test LLC") == "test"
        assert policy.normalize_vendor("Test Corp") == "test"
        assert policy.normalize_vendor("Test Ltd") == "test"

    def test_validate_filename_valid(self, policy: NARAPolicyNaming) -> None:
        """Test filename validation passes for valid names."""
        is_valid, error = policy.validate_filename("statement-chase-checking-20240115.pdf")
        assert is_valid
        assert error is None

    def test_validate_filename_too_long(self, policy: NARAPolicyNaming) -> None:
        """Test filename validation fails for too long names."""
        long_name = "a" * 300 + ".pdf"
        is_valid, error = policy.validate_filename(long_name)
        assert not is_valid
        assert "exceeds" in error.lower()


class TestNamingPolicyLoader:
    """Tests for NamingPolicyLoader."""

    def test_get_naming_loader(self) -> None:
        """Test singleton loader."""
        loader1 = get_naming_loader()
        loader2 = get_naming_loader()
        assert loader1 is loader2

    def test_list_available(self) -> None:
        """Test listing available policies."""
        loader = get_naming_loader()
        available = loader.list_available()
        assert "nara" in available

    def test_get_naming_policy_success(self) -> None:
        """Test getting policy by name."""
        policy = get_naming_policy("nara")
        assert isinstance(policy, NARAPolicyNaming)

    def test_get_naming_policy_not_found(self) -> None:
        """Test getting nonexistent policy raises error."""
        with pytest.raises(ValueError, match="Unknown naming policy"):
            get_naming_policy("nonexistent")
