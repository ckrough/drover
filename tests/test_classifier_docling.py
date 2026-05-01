"""Tests for DocumentClassifier content handling and prompt construction.

Verifies that classify() uses the content argument as prompt input and
that the max_prompt_chars cap is applied correctly.
"""

import pytest

from drover.classifier import DocumentClassifier
from drover.config import AIProvider, TaxonomyMode
from drover.models import RawClassification
from drover.taxonomy.household import HouseholdTaxonomy


class _StubStructuredLLM:
    """Records the messages passed to the structured LLM."""

    def __init__(self) -> None:
        self.last_messages: list[object] | None = None

    async def ainvoke(
        self,
        messages: list[object],
        config: object | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
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


def _make_classifier(max_prompt_chars: int = 20_000) -> DocumentClassifier:
    return DocumentClassifier(
        provider=AIProvider.OLLAMA,
        model="dummy",
        taxonomy=HouseholdTaxonomy(),
        taxonomy_mode=TaxonomyMode.FALLBACK,
        max_prompt_chars=max_prompt_chars,
    )


SENTINEL_FLAT = "FLAT_CONTENT_SENTINEL_PROF21O"


async def test_classify_uses_content_as_prompt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """classify() builds the prompt from the content argument."""
    classifier = _make_classifier()
    stub = _StubStructuredLLM()
    monkeypatch.setattr(classifier, "_get_structured_llm", lambda: stub)

    await classifier.classify(content=SENTINEL_FLAT)

    assert stub.last_messages is not None
    # Messages are now [SystemMessage, HumanMessage]; the document content
    # lives in the human message, taxonomy/rules in the system message.
    prompt = "\n\n".join(
        str(m.content)  # type: ignore[attr-defined]
        for m in stub.last_messages
    )
    assert SENTINEL_FLAT in prompt


async def test_classify_truncates_long_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """classify() applies head+tail truncation when content exceeds max_prompt_chars."""
    classifier = _make_classifier(max_prompt_chars=100)
    stub = _StubStructuredLLM()
    monkeypatch.setattr(classifier, "_get_structured_llm", lambda: stub)

    head_sentinel = "HEAD_SIGNAL"
    tail_sentinel = "TAIL_SIGNAL"
    # Build content that clearly exceeds 100 chars with distinct head and tail
    content = head_sentinel + "X" * 200 + tail_sentinel

    await classifier.classify(content=content)

    assert stub.last_messages is not None
    # Messages are now [SystemMessage, HumanMessage]; the document content
    # lives in the human message, taxonomy/rules in the system message.
    prompt = "\n\n".join(
        str(m.content)  # type: ignore[attr-defined]
        for m in stub.last_messages
    )
    assert head_sentinel in prompt
    assert tail_sentinel in prompt
    assert "[... truncated ...]" in prompt


async def test_classify_does_not_truncate_short_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """classify() passes content unchanged when it is within the char cap."""
    classifier = _make_classifier(max_prompt_chars=20_000)
    stub = _StubStructuredLLM()
    monkeypatch.setattr(classifier, "_get_structured_llm", lambda: stub)

    content = "short content"
    await classifier.classify(content=content)

    assert stub.last_messages is not None
    # Messages are now [SystemMessage, HumanMessage]; the document content
    # lives in the human message, taxonomy/rules in the system message.
    prompt = "\n\n".join(
        str(m.content)  # type: ignore[attr-defined]
        for m in stub.last_messages
    )
    assert content in prompt
    assert "[... truncated ...]" not in prompt
