"""Tests for Pydantic models."""

from drover.models import (
    ClassificationErrorResult,
    ClassificationResult,
    ErrorCode,
    RawClassification,
)


def test_classification_result_success():
    """Test creating a successful classification result.

    Example shows functional-domain-first principle: pet supply receipt
    goes to pets/expenses domain, not financial domain.
    """
    result = ClassificationResult(
        original="receipt.pdf",
        suggested_path=(
            "pets/expenses/receipt/receipt-petsmart-food_supplies-20250601.pdf"
        ),
        suggested_filename="receipt-petsmart-food_supplies-20250601.pdf",
        domain="pets",
        category="expenses",
        doctype="receipt",
        vendor="petsmart",
        date="20250601",
        subject="food supplies",
    )
    assert result.error is False
    assert result.error_code is None


def test_classification_error_from_exception():
    """Test creating error from exception."""
    error = ClassificationErrorResult.from_exception(
        filename="corrupt.pdf",
        code=ErrorCode.DOCUMENT_LOAD_FAILED,
        exception=ValueError("Cannot parse PDF"),
    )
    assert error.error is True
    assert error.error_code == ErrorCode.DOCUMENT_LOAD_FAILED
    assert "Cannot parse PDF" in error.error_message


def test_raw_classification():
    """Test raw classification model."""
    raw = RawClassification(
        domain="financial",
        category="banking",
        doctype="statement",
        vendor="Chase Bank",
        date="20250115",
        subject="checking account",
    )
    assert raw.vendor == "Chase Bank"  # Not normalized yet


def test_raw_classification_entity_defaults_to_empty():
    """Entity is optional and defaults to empty string."""
    raw = RawClassification(
        domain="financial",
        category="banking",
        doctype="statement",
        vendor="Chase Bank",
        date="20250115",
        subject="checking account",
    )
    assert raw.entity == ""


def test_raw_classification_entity_can_be_set():
    raw = RawClassification(
        domain="pets",
        category="medical",
        doctype="invoices",
        vendor="VCA Hospital",
        date="20250416",
        subject="annual checkup",
        entity="Sally",
    )
    assert raw.entity == "Sally"


def test_classification_result_entity_defaults_to_empty():
    result = ClassificationResult(
        original="scan.pdf",
        suggested_path="financial/banking/statements/x.pdf",
        suggested_filename="x.pdf",
        domain="financial",
        category="banking",
        doctype="statements",
        vendor="chase",
        date="20240115",
        subject="checking",
    )
    assert result.entity == ""
