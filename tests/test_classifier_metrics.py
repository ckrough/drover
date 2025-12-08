"""Tests for DocumentClassifier metrics integration with LangChain callbacks.
"""

import pytest

from drover.classifier import DocumentClassifier
from drover.config import AIProvider, TaxonomyMode
from drover.taxonomy.household import HouseholdTaxonomy


class _StubLLM:
    """Minimal async stub that records how it is invoked.

    This avoids importing real LangChain LLMs while still verifying that
    callbacks are passed via the runnable config instead of as a direct
    keyword argument.
    """

    def __init__(self) -> None:
        self.last_messages = None
        self.last_config = None
        self.last_kwargs = None

    async def ainvoke(self, messages, config=None, **kwargs):  # type: ignore[override]
        self.last_messages = messages
        self.last_config = config
        self.last_kwargs = kwargs

        class _Response:
            def __init__(self) -> None:
                self.content = (
                    '{"domain": "financial", "category": "banking", '
                    '"doctype": "statement", "vendor": "Bank", '
                    '"date": "20250101", "subject": "checking"}'
                )

        return _Response()


@pytest.mark.asyncio
async def test_classify_passes_callbacks_via_config(monkeypatch) -> None:
    """When collecting metrics, callbacks should be passed via config.

    This ensures compatibility with LangChain 0.3+ where passing callbacks
    both positionally and through config can lead to multiple values errors
    in `agenerate_prompt`.
    """

    taxonomy = HouseholdTaxonomy()
    classifier = DocumentClassifier(
        provider=AIProvider.OLLAMA,
        model="dummy",
        taxonomy=taxonomy,
        taxonomy_mode=TaxonomyMode.FALLBACK,
    )

    stub_llm = _StubLLM()
    monkeypatch.setattr(classifier, "_get_llm", lambda: stub_llm)

    classification, debug_info = await classifier.classify(
        "some document text", capture_debug=True, collect_metrics=True
    )

    assert classification.domain == "financial"
    assert classification.category == "banking"
    assert classification.doctype == "statement"
    assert debug_info is not None
    assert "metrics" in debug_info

    assert stub_llm.last_config is not None
    assert "callbacks" in stub_llm.last_config
    assert stub_llm.last_kwargs == {}
