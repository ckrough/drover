"""Tests for classification date validation and normalization."""

import pytest

from drover.dates import (
    NO_DATE_SENTINEL,
    is_valid_classification_date,
    normalize_classification_date,
)

# Confusable-digit strings included verbatim so the test exercises exactly
# the bytes a hallucinating LLM could emit. Both encode "20240115" using
# non-ASCII digit code points and must be rejected by the validator.
FULLWIDTH_DIGITS_DATE = "２０２４0115"  # noqa: RUF001
ARABIC_INDIC_DIGITS_DATE = "٢٠٢٤٠١١٥"


class TestIsValidClassificationDate:
    """Truth table for the shared classification-date validator."""

    @pytest.mark.parametrize(
        "value",
        [
            "20240115",  # ordinary real date
            "20240229",  # leap day in a leap year
            NO_DATE_SENTINEL,  # the no-date sentinel
        ],
    )
    def test_accepts_real_dates_and_sentinel(self, value: str) -> None:
        assert is_valid_classification_date(value) is True

    @pytest.mark.parametrize(
        "value",
        [
            "20240900",  # day == 00
            "20240015",  # month == 00
            "00000901",  # year == 0000 (month/day valid)
            "20240230",  # February 30 never exists
            "20230229",  # not a leap year
            "20241301",  # month 13
            "2024011",  # too short
            "202401155",  # too long
            "2024-01-15",  # not eight digits
            "abcdefgh",  # non-numeric
            "",  # empty
            FULLWIDTH_DIGITS_DATE,
            ARABIC_INDIC_DIGITS_DATE,
        ],
    )
    def test_rejects_partial_zero_and_impossible_dates(self, value: str) -> None:
        assert is_valid_classification_date(value) is False


class TestNormalizeClassificationDate:
    """normalize_classification_date returns a real date or the sentinel."""

    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("20240115", "20240115"),  # passes through
            ("240115", "20240115"),  # 6-digit YYMMDD expansion
            (NO_DATE_SENTINEL, NO_DATE_SENTINEL),  # sentinel preserved
            ("2024-01-15", "20240115"),  # strip separators
            ("2024011500", "20240115"),  # >8 digits truncated to leading 8
            ("20240900", NO_DATE_SENTINEL),  # day 00
            ("20240015", NO_DATE_SENTINEL),  # month 00
            ("00000901", NO_DATE_SENTINEL),  # year 0000
            ("20240230", NO_DATE_SENTINEL),  # impossible day
            ("", NO_DATE_SENTINEL),  # empty
            (None, NO_DATE_SENTINEL),  # None never crashes
            (FULLWIDTH_DIGITS_DATE, NO_DATE_SENTINEL),  # confusable digits rejected
        ],
    )
    def test_normalize(self, raw: str | None, expected: str) -> None:
        assert normalize_classification_date(raw) == expected
