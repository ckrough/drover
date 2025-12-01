"""Tests for Pydantic models."""

from drover.models import (
    ClassificationError,
    ClassificationResult,
    ErrorCode,
    RawClassification,
)


def test_classification_result_success():
    """Test creating a successful classification result."""
    result = ClassificationResult(
        original="receipt.pdf",
        suggested_path="financial/shopping/receipt/receipt-acme-groceries-20250601.pdf",
        domain="financial",
        category="shopping",
        doctype="receipt",
        vendor="acme",
        date="20250601",
        subject="groceries",
    )
    assert result.error is False
    assert result.error_code is None


def test_classification_error_from_exception():
    """Test creating error from exception."""
    error = ClassificationError.from_exception(
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
