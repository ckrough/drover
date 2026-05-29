"""Tests for Pydantic models."""

import pytest

from drover.dates import NO_DATE_SENTINEL
from drover.models import (
    ClassificationErrorResult,
    ClassificationResult,
    ErrorCode,
    RawClassification,
)

# Confusable-digit string encoding "20240115" with fullwidth code points,
# used to verify the model-boundary normalizer rejects non-ASCII digits.
_FULLWIDTH_DIGITS_DATE = "２０２４0115"  # noqa: RUF001


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


@pytest.mark.parametrize(
    ("raw_date", "expected"),
    [
        ("20240115", "20240115"),  # real date preserved
        (NO_DATE_SENTINEL, NO_DATE_SENTINEL),  # sentinel preserved
        ("20240900", NO_DATE_SENTINEL),  # day 00 normalized
        ("20240015", NO_DATE_SENTINEL),  # month 00 normalized
        ("00000901", NO_DATE_SENTINEL),  # year 0000 normalized
        ("20240230", NO_DATE_SENTINEL),  # impossible day normalized
        (_FULLWIDTH_DIGITS_DATE, NO_DATE_SENTINEL),  # confusable digits normalized
        ("240115", "20240115"),  # 6-digit YYMMDD expanded
    ],
)
def test_raw_classification_normalizes_date_at_boundary(
    raw_date: str, expected: str
) -> None:
    """The LLM-supplied date is normalized before any downstream consumer reads it."""
    raw = RawClassification(
        domain="financial",
        category="banking",
        doctype="statement",
        vendor="chase",
        date=raw_date,
        subject="checking",
    )
    assert raw.date == expected


def test_classification_result_normalizes_date_at_boundary() -> None:
    """ClassificationResult also normalizes its date for safe downstream reuse."""
    result = ClassificationResult(
        original="doc.pdf",
        suggested_path="financial/banking/statement/doc.pdf",
        suggested_filename="doc.pdf",
        domain="financial",
        category="banking",
        doctype="statement",
        vendor="chase",
        date="20240900",  # day 00 from the LLM
        subject="checking",
    )
    assert result.date == NO_DATE_SENTINEL
