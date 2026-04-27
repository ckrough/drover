"""Per-chunk score aggregation for the NLI classifier (Phase 2).

When a document is split into multiple chunks, each chunk is scored against
the same hypothesis. These functions combine those per-chunk scores into a
single per-label score that the classifier can argmax over.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from drover.config import Aggregation

if TYPE_CHECKING:
    from collections.abc import Callable


def aggregate_max(scores: list[float]) -> float:
    """Return the highest score, or 0.0 for empty input."""
    if not scores:
        return 0.0
    return max(scores)


def aggregate_mean(scores: list[float]) -> float:
    """Return the arithmetic mean, or 0.0 for empty input."""
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def aggregate_weighted(scores: list[float]) -> float:
    """Return an endpoint-weighted mean.

    First and last chunks weigh 2; middle chunks weigh 1. This favors the
    introduction and conclusion of structured documents (statements, invoices,
    contracts) where the document type signal usually concentrates. With a
    single chunk, returns the chunk score unchanged. Empty input returns 0.0.
    """
    if not scores:
        return 0.0
    if len(scores) == 1:
        return scores[0]

    weights = [2.0] + [1.0] * (len(scores) - 2) + [2.0]
    weighted_sum = sum(s * w for s, w in zip(scores, weights, strict=True))
    return weighted_sum / sum(weights)


AGGREGATORS: dict[Aggregation, Callable[[list[float]], float]] = {
    Aggregation.MAX: aggregate_max,
    Aggregation.MEAN: aggregate_mean,
    Aggregation.WEIGHTED: aggregate_weighted,
}
