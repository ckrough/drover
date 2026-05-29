"""Tests for the evaluation framework's data models."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest
from pydantic import ValidationError

from drover.dates import NO_DATE_SENTINEL
from drover.evaluation import ClassificationEvaluator, GroundTruthEntry

if TYPE_CHECKING:
    from pathlib import Path


class TestGroundTruthEntryDateValidation:
    """GroundTruthEntry rejects partial-zero and impossible dates."""

    def _entry(self, date: str | None) -> GroundTruthEntry:
        return GroundTruthEntry.model_validate(
            {
                "filename": "doc.pdf",
                "domain": "financial",
                "category": "banking",
                "doctype": "statement",
                "date": date,
            }
        )

    @pytest.mark.parametrize("date", ["20240115", NO_DATE_SENTINEL, None])
    def test_accepts_real_date_sentinel_and_missing(self, date: str | None) -> None:
        assert self._entry(date).date == date

    @pytest.mark.parametrize("date", ["20240900", "20240015", "00000901"])
    def test_rejects_partial_zero_dates(self, date: str) -> None:
        with pytest.raises(ValidationError):
            self._entry(date)


class TestGroundTruthLoaderSkipsBadDates:
    """A partial-zero ground-truth line is skipped, not fatal to the load."""

    def test_bad_date_line_is_skipped_not_fatal(self, tmp_path: Path) -> None:
        good = {
            "filename": "good.pdf",
            "domain": "financial",
            "category": "banking",
            "doctype": "statement",
            "date": "20240115",
        }
        bad = {**good, "filename": "bad.pdf", "date": "20240900"}
        gt = tmp_path / "ground_truth.jsonl"
        gt.write_text(json.dumps(good) + "\n" + json.dumps(bad) + "\n")

        evaluator = ClassificationEvaluator(ground_truth_path=str(gt))

        assert "good.pdf" in evaluator.ground_truth
        assert "bad.pdf" not in evaluator.ground_truth
