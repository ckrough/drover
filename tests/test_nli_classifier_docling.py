"""Tests for NLI classifier docling integration (prof-epk).

When `docling_doc` is provided, the NLI classifier should chunk via
Docling's `HybridChunker` (section-aware) instead of the configured
token-window strategy. When `None`, behavior is unchanged.

These tests do not load the real DeBERTa model; they patch the helper
methods that touch Docling and the entailment scorer.
"""

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from drover.config import ChunkStrategy, TaxonomyMode
from drover.nli_classifier import NLIDocumentClassifier
from drover.taxonomy.household import HouseholdTaxonomy


@pytest.fixture
def taxonomy() -> HouseholdTaxonomy:
    return HouseholdTaxonomy()


def _make_classifier(taxonomy: HouseholdTaxonomy) -> NLIDocumentClassifier:
    return NLIDocumentClassifier(
        taxonomy=taxonomy,
        taxonomy_mode=TaxonomyMode.FALLBACK,
        chunk_strategy=ChunkStrategy.TRUNCATE,
        max_tokens=450,
    )


def _mock_score(premise: str, hypothesis: str) -> float:
    if "financial" in hypothesis.lower():
        return 0.9
    if "banking" in hypothesis.lower():
        return 0.85
    if "statement" in hypothesis.lower():
        return 0.8
    return 0.1


def test_get_chunks_uses_hybrid_when_docling_doc_provided(
    taxonomy: HouseholdTaxonomy,
) -> None:
    """`_get_chunks` routes to HybridChunker for parsed documents."""
    classifier = _make_classifier(taxonomy)
    fake_doc = SimpleNamespace()
    expected = ["# Section A\n\nbody", "## Section B\n\nbody2"]

    with patch.object(
        classifier, "_chunk_with_hybrid", return_value=expected
    ) as hybrid:
        result = classifier._get_chunks("fallback flat text", docling_doc=fake_doc)

    hybrid.assert_called_once_with(fake_doc)
    assert result == expected


def test_get_chunks_falls_back_to_strategy_when_docling_doc_is_none(
    taxonomy: HouseholdTaxonomy,
) -> None:
    """`_get_chunks` keeps the legacy registry path for flat text."""
    classifier = _make_classifier(taxonomy)

    with (
        patch.object(
            classifier, "_chunk_with_hybrid", return_value=["should-not-be-used"]
        ) as hybrid,
        patch.object(classifier, "_get_model") as get_model,
        patch(
            "drover.nli_classifier.CHUNKERS",
            {ChunkStrategy.TRUNCATE: lambda content, _tok, _n: [content]},
        ),
    ):
        get_model.return_value = (object(), object())
        result = classifier._get_chunks("flat text", docling_doc=None)

    hybrid.assert_not_called()
    assert result == ["flat text"]


def test_classify_sync_uses_hybrid_chunks_and_records_strategy(
    taxonomy: HouseholdTaxonomy,
) -> None:
    """Hybrid path surfaces chunks to the scorer and labels itself in debug."""
    classifier = _make_classifier(taxonomy)
    fake_doc = SimpleNamespace()
    section_chunks = [
        "# Bank Statement\n\nAccount summary",
        "## Transactions\n\nDeposit",
    ]

    with (
        patch.object(classifier, "_compute_entailment_score", side_effect=_mock_score),
        patch.object(classifier, "_chunk_with_hybrid", return_value=section_chunks),
    ):
        _, debug = classifier._classify_sync(
            "ignored flat content",
            capture_debug=True,
            docling_doc=fake_doc,
        )

    assert debug is not None
    assert debug["chunk_strategy"] == "hybrid"
    assert debug["chunk_count"] == 2


def test_classify_sync_uses_strategy_registry_when_docling_doc_is_none(
    taxonomy: HouseholdTaxonomy,
) -> None:
    """Without a docling_doc, the original chunk_strategy label is preserved."""
    classifier = _make_classifier(taxonomy)

    with (
        patch.object(classifier, "_compute_entailment_score", side_effect=_mock_score),
        patch.object(classifier, "_get_chunks", return_value=["one chunk"]),
    ):
        _, debug = classifier._classify_sync(
            "flat content",
            capture_debug=True,
            docling_doc=None,
        )

    assert debug is not None
    assert debug["chunk_strategy"] == "truncate"


def test_build_hybrid_chunker_aligns_tokenizer_with_nli_model(
    taxonomy: HouseholdTaxonomy,
) -> None:
    """HybridChunker uses the NLI cross-encoder's tokenizer.

    Aligning the chunker tokenizer with the NLI model means chunk token
    counts match the entailment scorer's window — so chunks fit without
    silent truncation between chunking and inference.
    """
    classifier = NLIDocumentClassifier(
        taxonomy=taxonomy,
        model_name="cross-encoder/nli-deberta-v3-base",
        max_tokens=450,
    )

    captured: dict[str, object] = {}

    class _FakeTokenizer:
        @classmethod
        def from_pretrained(cls, **kwargs: object) -> "_FakeTokenizer":
            captured.update(kwargs)
            return cls()

    class _FakeChunker:
        def __init__(self, tokenizer: object, merge_peers: bool = False) -> None:
            captured["tokenizer_obj"] = tokenizer
            captured["merge_peers"] = merge_peers

    with (
        patch("docling.chunking.HybridChunker", _FakeChunker),
        patch(
            "docling_core.transforms.chunker.tokenizer.huggingface.HuggingFaceTokenizer",
            _FakeTokenizer,
        ),
    ):
        classifier._build_hybrid_chunker()

    assert captured["model_name"] == "cross-encoder/nli-deberta-v3-base"
    assert captured["max_tokens"] == 450
    assert captured["merge_peers"] is True
