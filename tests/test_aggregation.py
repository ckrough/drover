"""Tests for per-chunk score aggregation methods (Phase 2 NLI)."""

from __future__ import annotations

import pytest

from drover.aggregation import (
    AGGREGATORS,
    aggregate_max,
    aggregate_mean,
    aggregate_weighted,
)
from drover.config import Aggregation


class TestAggregateMax:
    def test_returns_max_of_scores(self) -> None:
        assert aggregate_max([0.1, 0.9, 0.5]) == pytest.approx(0.9)

    def test_single_score(self) -> None:
        assert aggregate_max([0.42]) == pytest.approx(0.42)

    def test_empty_returns_zero(self) -> None:
        assert aggregate_max([]) == 0.0


class TestAggregateMean:
    def test_arithmetic_mean(self) -> None:
        assert aggregate_mean([0.2, 0.4, 0.6]) == pytest.approx(0.4)

    def test_single_score(self) -> None:
        assert aggregate_mean([0.7]) == pytest.approx(0.7)

    def test_empty_returns_zero(self) -> None:
        assert aggregate_mean([]) == 0.0


class TestAggregateWeighted:
    def test_single_chunk_passthrough(self) -> None:
        """Single-chunk input returns the chunk score unchanged."""
        assert aggregate_weighted([0.42]) == pytest.approx(0.42)

    def test_empty_returns_zero(self) -> None:
        assert aggregate_weighted([]) == 0.0

    def test_endpoints_weighted_double(self) -> None:
        """First/last weight 2x, middle 1x. For [1.0, 0.0, 1.0]:
        weighted mean = (2*1.0 + 1*0.0 + 2*1.0) / (2+1+2) = 4.0 / 5 = 0.8."""
        result = aggregate_weighted([1.0, 0.0, 1.0])
        assert result == pytest.approx(0.8)

    def test_weighted_strictly_above_mean_when_endpoints_higher(self) -> None:
        """If endpoints score higher than middle, weighted > mean."""
        scores = [1.0, 0.0, 1.0]
        assert aggregate_weighted(scores) > aggregate_mean(scores)

    def test_two_chunks_treated_as_both_endpoints(self) -> None:
        """With exactly two chunks, both are endpoints (weight 2 each).
        Weighted mean equals plain mean: (2*0.4 + 2*0.6) / 4 = 0.5."""
        assert aggregate_weighted([0.4, 0.6]) == pytest.approx(0.5)


class TestAggregatorsRegistry:
    def test_registry_covers_all_enum_values(self) -> None:
        """Every Aggregation enum value maps to a function."""
        for member in Aggregation:
            assert member in AGGREGATORS
            assert callable(AGGREGATORS[member])

    def test_max_dispatch(self) -> None:
        assert AGGREGATORS[Aggregation.MAX]([0.1, 0.9]) == pytest.approx(0.9)

    def test_mean_dispatch(self) -> None:
        assert AGGREGATORS[Aggregation.MEAN]([0.2, 0.4]) == pytest.approx(0.3)

    def test_weighted_dispatch(self) -> None:
        assert AGGREGATORS[Aggregation.WEIGHTED]([0.42]) == pytest.approx(0.42)
