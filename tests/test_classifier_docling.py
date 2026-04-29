"""Tests for DocumentClassifier docling-doc plumbing (prof-21o).

When the loader provides a parsed `DoclingDocument`, the LLM classifier
should prompt the model with the structure-preserving markdown export
instead of the flat sampled-pages blob. When `docling_doc` is `None`,
the prompt is byte-identical to the prior behavior.
"""

from types import SimpleNamespace

import pytest

from drover.classifier import DocumentClassifier
from drover.config import AIProvider, TaxonomyMode
from drover.models import RawClassification
from drover.taxonomy.household import HouseholdTaxonomy


class _StubStructuredLLM:
    """Records the messages passed to the structured LLM."""

    def __init__(self) -> None:
        self.last_messages: list[object] | None = None

    async def ainvoke(self, messages, config=None, **kwargs):  # type: ignore[no-untyped-def]
        self.last_messages = messages

        class _Raw:
            content = (
                '{"domain": "financial", "category": "banking", '
                '"doctype": "statement", "vendor": "Bank", '
                '"date": "20250101", "subject": "checking"}'
            )

        return {
            "raw": _Raw(),
            "parsed": RawClassification(
                domain="financial",
                category="banking",
                doctype="statement",
                vendor="Bank",
                date="20250101",
                subject="checking",
            ),
            "parsing_error": None,
        }


def _make_classifier() -> DocumentClassifier:
    return DocumentClassifier(
        provider=AIProvider.OLLAMA,
        model="dummy",
        taxonomy=HouseholdTaxonomy(),
        taxonomy_mode=TaxonomyMode.FALLBACK,
    )


SENTINEL_FLAT = "FLAT_CONTENT_SENTINEL_PROF21O"
SENTINEL_MD = "# Heading From Docling\n\n## Subheading\n\nBody text."


@pytest.mark.asyncio
async def test_classify_uses_flat_content_when_docling_doc_is_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifier = _make_classifier()
    stub = _StubStructuredLLM()
    monkeypatch.setattr(classifier, "_get_structured_llm", lambda: stub)

    await classifier.classify(content=SENTINEL_FLAT, docling_doc=None)

    assert stub.last_messages is not None
    prompt = stub.last_messages[0].content  # type: ignore[attr-defined]
    assert SENTINEL_FLAT in prompt
    assert SENTINEL_MD not in prompt


@pytest.mark.asyncio
async def test_classify_default_kwarg_matches_explicit_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The default (no docling_doc passed) yields the same prompt as None."""
    classifier_default = _make_classifier()
    stub_default = _StubStructuredLLM()
    monkeypatch.setattr(classifier_default, "_get_structured_llm", lambda: stub_default)
    await classifier_default.classify(content=SENTINEL_FLAT)
    prompt_default = stub_default.last_messages[0].content  # type: ignore[attr-defined,index]

    classifier_none = _make_classifier()
    stub_none = _StubStructuredLLM()
    monkeypatch.setattr(classifier_none, "_get_structured_llm", lambda: stub_none)
    await classifier_none.classify(content=SENTINEL_FLAT, docling_doc=None)
    prompt_none = stub_none.last_messages[0].content  # type: ignore[attr-defined,index]

    assert prompt_default == prompt_none


@pytest.mark.asyncio
async def test_classify_uses_markdown_when_docling_doc_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    classifier = _make_classifier()
    stub = _StubStructuredLLM()
    monkeypatch.setattr(classifier, "_get_structured_llm", lambda: stub)

    fake_doc = SimpleNamespace(export_to_markdown=lambda: SENTINEL_MD)

    await classifier.classify(content=SENTINEL_FLAT, docling_doc=fake_doc)

    assert stub.last_messages is not None
    prompt = stub.last_messages[0].content  # type: ignore[attr-defined]
    assert "# Heading From Docling" in prompt
    assert "## Subheading" in prompt
    # Flat content must be replaced, not appended.
    assert SENTINEL_FLAT not in prompt
