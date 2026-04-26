"""Tests for the comparison helpers in scripts/eval_runner.py."""

from __future__ import annotations

from typing import Any

import pytest

from drover.models import ClassificationResult

eval_runner = pytest.importorskip("eval_runner")
ExpectedClassification = eval_runner.ExpectedClassification
compare_results = eval_runner.compare_results


def _result(**overrides: Any) -> ClassificationResult:
    base: dict[str, Any] = {
        "original": "doc.pdf",
        "suggested_path": "financial/banking/statement/file.pdf",
        "suggested_filename": "file.pdf",
        "domain": "financial",
        "category": "banking",
        "doctype": "statement",
        "vendor": "Chase",
        "date": "20240115",
        "subject": "account summary",
    }
    base.update(overrides)
    return ClassificationResult(**base)


def _expected(**overrides: Any) -> ExpectedClassification:
    base: dict[str, Any] = {
        "domain": "financial",
        "category": "banking",
        "doctype": "statement",
        "vendor": "Chase",
        "date": "20240115",
        "subject": "account summary",
    }
    base.update(overrides)
    return ExpectedClassification(**base)


class TestSubjectComparison:
    def test_identical_subjects_match(self) -> None:
        matches = compare_results(
            _result(subject="pet supplies"), _expected(subject="pet supplies")
        )
        assert matches["subject"] is True

    def test_predicted_superset_matches(self) -> None:
        matches = compare_results(
            _result(subject="dog food and pet supplies"),
            _expected(subject="pet supplies"),
        )
        assert matches["subject"] is True

    def test_disjoint_subjects_do_not_match(self) -> None:
        matches = compare_results(
            _result(subject="office visit lab tests"),
            _expected(subject="medical services"),
        )
        assert matches["subject"] is False

    def test_partial_overlap_does_not_match(self) -> None:
        matches = compare_results(
            _result(subject="medical billing"),
            _expected(subject="medical services"),
        )
        assert matches["subject"] is False

    def test_subject_match_is_case_insensitive(self) -> None:
        matches = compare_results(
            _result(subject="Dog Food And Pet Supplies"),
            _expected(subject="pet supplies"),
        )
        assert matches["subject"] is True

    def test_subject_punctuation_ignored(self) -> None:
        matches = compare_results(
            _result(subject="dog-food, and pet supplies!"),
            _expected(subject="pet supplies"),
        )
        assert matches["subject"] is True


class TestVendorComparison:
    def test_identical_vendors_match(self) -> None:
        matches = compare_results(
            _result(vendor="PetSmart"), _expected(vendor="PetSmart")
        )
        assert matches["vendor"] is True

    def test_case_difference_matches(self) -> None:
        matches = compare_results(
            _result(vendor="PETSMART"), _expected(vendor="PetSmart")
        )
        assert matches["vendor"] is True

    def test_punctuation_difference_matches(self) -> None:
        matches = compare_results(
            _result(vendor="SmartHub Inc."),
            _expected(vendor="smarthub inc"),
        )
        assert matches["vendor"] is True

    def test_whitespace_collapse_matches(self) -> None:
        matches = compare_results(
            _result(vendor="Northern  Virginia  Medical Center"),
            _expected(vendor="Northern Virginia Medical Center"),
        )
        assert matches["vendor"] is True

    def test_different_vendors_do_not_match(self) -> None:
        matches = compare_results(_result(vendor="PetSmart"), _expected(vendor="Petco"))
        assert matches["vendor"] is False


class TestStrictFields:
    def test_domain_strict_case(self) -> None:
        matches = compare_results(
            _result(domain="financial"), _expected(domain="Financial")
        )
        assert matches["domain"] is False

    def test_category_strict(self) -> None:
        matches = compare_results(
            _result(category="banking"), _expected(category="bank")
        )
        assert matches["category"] is False

    def test_date_strict(self) -> None:
        matches = compare_results(_result(date="20240115"), _expected(date="20240116"))
        assert matches["date"] is False


class TestReturnedShape:
    def test_returns_all_comparison_fields_in_order(self) -> None:
        matches = compare_results(_result(), _expected())
        assert list(matches.keys()) == eval_runner.COMPARISON_FIELDS

    def test_full_match_returns_all_true(self) -> None:
        matches = compare_results(_result(), _expected())
        assert all(matches.values())
