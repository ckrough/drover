"""Validation and normalization for classification date strings.

A classification date is either the ``00000000`` "no date" sentinel or an
eight-digit ASCII ``YYYYMMDD`` string naming a real calendar day. Partial-zero
dates (``20240900`` day 00, ``20240015`` month 00, ``00000901`` year 0000),
impossible days (``20240230``), and non-ASCII digit shapes (fullwidth,
Arabic-Indic) indicate a hallucinated or sloppily extracted date and are
not accepted outside the sentinel.
"""

from datetime import date

NO_DATE_SENTINEL = "00000000"

_ASCII_DIGITS = frozenset("0123456789")


def is_valid_classification_date(value: str) -> bool:
    """Return whether ``value`` is the no-date sentinel or a real YYYYMMDD date.

    Valid inputs are exactly ``"00000000"`` (no date available) or an
    eight-character ASCII-digit ``YYYYMMDD`` string that names a real
    calendar day: year >= 1, month 01-12, and a day valid for that month
    with leap years honored. Anything else - partial-zero components,
    impossible days like February 30, non-ASCII digit characters, wrong
    lengths, or non-numeric strings - is rejected.

    Args:
        value: The date string to validate.

    Returns:
        True if the string is the sentinel or a real calendar date.
    """
    if value == NO_DATE_SENTINEL:
        return True
    if len(value) != 8 or not all(c in _ASCII_DIGITS for c in value):
        return False
    try:
        date(int(value[:4]), int(value[4:6]), int(value[6:8]))
    except ValueError:
        return False
    return True


def normalize_classification_date(raw: str | None) -> str:
    """Normalize a raw date string to a canonical YYYYMMDD or the sentinel.

    Strips non-ASCII-digit characters, applies the 6-digit ``YYMMDD`` to
    ``20YYMMDD`` expansion, truncates inputs of 8 or more digits to the
    leading eight, and validates the result with
    :func:`is_valid_classification_date`. Anything that fails validation
    (including ``None`` and the empty string) collapses to the
    :data:`NO_DATE_SENTINEL`, so callers can treat the return as always
    safe to embed in a filename, tag, or downstream record.

    Args:
        raw: An LLM- or operator-supplied date string, or ``None``.

    Returns:
        A real YYYYMMDD date or :data:`NO_DATE_SENTINEL`.
    """
    if raw is None:
        return NO_DATE_SENTINEL
    digits = "".join(c for c in raw if c in _ASCII_DIGITS)
    if len(digits) == 6:
        digits = f"20{digits}"
    candidate = digits[:8]
    if is_valid_classification_date(candidate):
        return candidate
    return NO_DATE_SENTINEL
