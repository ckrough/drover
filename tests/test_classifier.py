"""Tests for DocumentClassifier — truncation, streaming, and template validation.

Covers:
- _truncate_content: cap enforcement, boundary math, non-ASCII safety
- classify_streaming: happy path, streaming-exception fallback, structured-output fallback
- render_messages: XOR heading guard (P3-1)
- __init__: max_prompt_chars <= 0 raises ValueError (P0-1)
"""

from __future__ import annotations

import pytest

from drover.classifier import (
    DocumentClassifier,
    LLMParseError,
    TemplateError,
)
from drover.config import AIProvider, TaxonomyMode
from drover.models import RawClassification
from drover.taxonomy.household import HouseholdTaxonomy

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_GOOD_CLASSIFICATION = RawClassification(
    domain="financial",
    category="banking",
    doctype="statement",
    vendor="Bank",
    date="20250101",
    subject="checking",
)

_GOOD_STRUCTURED_RESULT: dict[str, object] = {
    "raw": type("_Raw", (), {"content": '{"domain": "financial", ...}'})(),
    "parsed": _GOOD_CLASSIFICATION,
    "parsing_error": None,
}


class _StubStructuredLLM:
    """Minimal structured-LLM stub that returns a valid RawClassification."""

    async def ainvoke(
        self,
        messages: list[object],
        config: object | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        return dict(_GOOD_STRUCTURED_RESULT)


class _FailingStreamLLM:
    """LLM stub whose astream raises mid-stream; ainvoke succeeds normally."""

    async def ainvoke(
        self,
        messages: list[object],
        config: object | None = None,
        **kwargs: object,
    ) -> object:
        # Used by _invoke_with_retry fallback — not called in streaming path
        raise AssertionError("ainvoke should not be called on the base LLM here")

    async def astream(self, messages: list[object], **kwargs: object):  # type: ignore[override]
        yield type("Chunk", (), {"content": "tok1"})()
        raise ConnectionError("stream dropped mid-flight")


class _HappyStreamLLM:
    """LLM stub that streams two tokens then finishes cleanly."""

    def __init__(self) -> None:
        self.tokens_seen: list[str] = []

    async def astream(self, messages: list[object], **kwargs: object):  # type: ignore[override]
        for tok in ("hello", " world"):
            yield type("Chunk", (), {"content": tok})()


class _FailingStructuredLLM:
    """Structured-LLM stub that always raises (simulates total structured-output failure)."""

    async def ainvoke(
        self,
        messages: list[object],
        config: object | None = None,
        **kwargs: object,
    ) -> dict[str, object]:
        raise ConnectionError("structured output service unavailable")


def _make_classifier(max_prompt_chars: int = 20_000) -> DocumentClassifier:
    """Return a classifier wired to HouseholdTaxonomy with a dummy model."""
    return DocumentClassifier(
        provider=AIProvider.OLLAMA,
        model="dummy",
        taxonomy=HouseholdTaxonomy(),
        taxonomy_mode=TaxonomyMode.FALLBACK,
        max_prompt_chars=max_prompt_chars,
    )


# ---------------------------------------------------------------------------
# P0-1: __init__ raises ValueError when max_prompt_chars <= 0
# ---------------------------------------------------------------------------


class TestMaxPromptCharsValidation:
    """DocumentClassifier.__init__ must reject non-positive max_prompt_chars."""

    def test_zero_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="max_prompt_chars"):
            _make_classifier(max_prompt_chars=0)

    def test_negative_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="max_prompt_chars"):
            _make_classifier(max_prompt_chars=-1)

    def test_one_is_accepted(self) -> None:
        """Positive values, even tiny ones, must not raise."""
        classifier = _make_classifier(max_prompt_chars=1)
        assert classifier.max_prompt_chars == 1

    def test_default_is_accepted(self) -> None:
        classifier = _make_classifier()
        assert classifier.max_prompt_chars == 20_000


# ---------------------------------------------------------------------------
# P1-2: _truncate_content
# ---------------------------------------------------------------------------


class TestTruncateContent:
    """Unit tests for DocumentClassifier._truncate_content."""

    def test_short_content_returned_unchanged(self) -> None:
        classifier = _make_classifier(max_prompt_chars=100)
        content = "short"
        assert classifier._truncate_content(content) == content

    def test_content_equal_to_cap_returned_unchanged(self) -> None:
        classifier = _make_classifier(max_prompt_chars=50)
        content = "x" * 50
        assert classifier._truncate_content(content) == content

    def test_content_exceeding_cap_is_truncated(self) -> None:
        cap = 100
        classifier = _make_classifier(max_prompt_chars=cap)
        content = "A" * 200
        result = classifier._truncate_content(content)
        assert "[... truncated ...]" in result

    def test_head_and_tail_both_present_after_truncation(self) -> None:
        cap = 100
        classifier = _make_classifier(max_prompt_chars=cap)
        head_sentinel = "HEADSTART"
        tail_sentinel = "TAILEND00"
        content = head_sentinel + "M" * 200 + tail_sentinel
        result = classifier._truncate_content(content)
        assert head_sentinel in result
        assert tail_sentinel in result

    def test_head_tail_char_counts_match_spec(self) -> None:
        """Default 20K cap: head=14K chars, tail=6K chars."""
        cap = 20_000
        classifier = _make_classifier(max_prompt_chars=cap)
        content = "H" * 30_000
        result = classifier._truncate_content(content)
        # Strip the sentinel to measure pure head/tail
        sentinel = "\n\n[... truncated ...]\n\n"
        assert sentinel in result
        head_part, tail_part = result.split(sentinel, 1)
        expected_head = (cap * 14) // 20  # 14000
        expected_tail = cap - expected_head  # 6000
        assert len(head_part) == expected_head
        assert len(tail_part) == expected_tail

    def test_non_ascii_boundary_slices_safely(self) -> None:
        """Emoji and multi-byte chars at the split boundary must not raise."""
        cap = 20
        classifier = _make_classifier(max_prompt_chars=cap)
        # Build content that puts multi-byte chars near the head/tail boundary.
        # Each emoji is one Python str codepoint (len=1), so this is safe.
        content = "x" * 5 + "😀" * 30 + "x" * 5
        # Should not raise; result type is str
        result = classifier._truncate_content(content)
        assert isinstance(result, str)

    def test_truncated_output_does_not_exceed_cap_significantly(self) -> None:
        """Result length should be close to cap (sentinel overhead is acceptable)."""
        cap = 200
        classifier = _make_classifier(max_prompt_chars=cap)
        content = "Z" * 1_000
        result = classifier._truncate_content(content)
        sentinel = "\n\n[... truncated ...]\n\n"
        # head + tail = cap; sentinel adds a fixed overhead
        assert len(result) == cap + len(sentinel)


# ---------------------------------------------------------------------------
# P1-4: classify_streaming
# ---------------------------------------------------------------------------


class TestClassifyStreaming:
    """Tests for the two-phase streaming + finalizer path."""

    async def test_happy_path_tokens_emitted_and_result_returned(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Happy path: on_token receives streamed tokens; finalizer returns valid result."""
        classifier = _make_classifier()
        stream_stub = _HappyStreamLLM()
        structured_stub = _StubStructuredLLM()

        monkeypatch.setattr(classifier, "_get_llm", lambda: stream_stub)
        monkeypatch.setattr(classifier, "_get_structured_llm", lambda: structured_stub)

        received: list[str] = []
        result = await classifier.classify_streaming(
            content="some document text",
            on_token=received.append,
        )

        assert received == ["hello", " world"]
        assert isinstance(result, RawClassification)
        assert result.domain == "financial"

    async def test_streaming_exception_finalizer_still_runs(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When astream raises mid-stream, the finalizer still runs and returns a result."""
        classifier = _make_classifier()
        fail_stream = _FailingStreamLLM()
        structured_stub = _StubStructuredLLM()

        monkeypatch.setattr(classifier, "_get_llm", lambda: fail_stream)
        monkeypatch.setattr(classifier, "_get_structured_llm", lambda: structured_stub)

        received: list[str] = []
        # Must not raise despite the stream failure
        result = await classifier.classify_streaming(
            content="some document text",
            on_token=received.append,
        )

        # One token was emitted before the error
        assert received == ["tok1"]
        # Finalizer still produced a valid classification
        assert isinstance(result, RawClassification)
        assert result.domain == "financial"

    async def test_structured_output_failure_uses_parse_response_fallback(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When _invoke_structured_with_retry raises, _parse_response fallback is used."""
        classifier = _make_classifier()
        stream_stub = _HappyStreamLLM()

        monkeypatch.setattr(classifier, "_get_llm", lambda: stream_stub)

        # Stub _invoke_structured_with_retry to return a result with no parsed field,
        # causing the fallback branch to exercise _parse_response.
        raw_json = (
            '{"domain": "financial", "category": "banking", "doctype": "statement",'
            ' "vendor": "FallbackBank", "date": "20240101", "subject": "test doc"}'
        )

        class _Raw:
            content = raw_json

        async def _fake_invoke_structured(
            messages: object, config: object
        ) -> dict[str, object]:
            return {"raw": _Raw(), "parsed": None, "parsing_error": "forced failure"}

        monkeypatch.setattr(
            classifier, "_invoke_structured_with_retry", _fake_invoke_structured
        )

        result = await classifier.classify_streaming(content="some document text")

        assert isinstance(result, RawClassification)
        assert result.vendor == "FallbackBank"

    async def test_structured_output_failure_no_raw_raises_llm_parse_error(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """When structured output fails and no raw response is available, LLMParseError is raised."""
        classifier = _make_classifier()
        stream_stub = _HappyStreamLLM()

        monkeypatch.setattr(classifier, "_get_llm", lambda: stream_stub)

        async def _fake_invoke_structured(
            messages: object, config: object
        ) -> dict[str, object]:
            return {"raw": None, "parsed": None, "parsing_error": "forced failure"}

        monkeypatch.setattr(
            classifier, "_invoke_structured_with_retry", _fake_invoke_structured
        )

        with pytest.raises(LLMParseError, match="no raw response"):
            await classifier.classify_streaming(content="some document text")


# ---------------------------------------------------------------------------
# P3-1: render_messages XOR guard
# ---------------------------------------------------------------------------


class TestRenderMessagesHeadingGuard:
    """render_messages must raise TemplateError when exactly one section heading is present."""

    def _make_template_with_content(self, raw_content: str) -> object:
        """Return a PromptTemplate-like stub with pre-loaded content."""
        from drover.classifier import PromptTemplate

        tpl = object.__new__(PromptTemplate)
        # Bypass _load() by setting internals directly
        tpl._content = raw_content  # type: ignore[attr-defined]
        tpl._frontmatter = {}  # type: ignore[attr-defined]
        tpl._resource_path = None  # type: ignore[attr-defined]
        tpl.template_path = None  # type: ignore[attr-defined]
        return tpl

    def test_only_system_heading_raises_template_error(self) -> None:
        from drover.classifier import (
            SYSTEM_SECTION_HEADING,
            PromptTemplate,
        )

        tpl = self._make_template_with_content(
            f"{SYSTEM_SECTION_HEADING}\n\nsome content {{taxonomy_menu}} {{document_content}}"
        )
        assert isinstance(tpl, PromptTemplate)
        with pytest.raises(TemplateError, match="both"):
            tpl.render_messages(taxonomy_menu="tm", document_content="doc")

    def test_only_human_heading_raises_template_error(self) -> None:
        from drover.classifier import (
            HUMAN_SECTION_HEADING,
            PromptTemplate,
        )

        tpl = self._make_template_with_content(
            f"{HUMAN_SECTION_HEADING}\n\nsome content {{taxonomy_menu}} {{document_content}}"
        )
        assert isinstance(tpl, PromptTemplate)
        with pytest.raises(TemplateError, match="both"):
            tpl.render_messages(taxonomy_menu="tm", document_content="doc")

    def test_both_headings_succeeds(self) -> None:
        from drover.classifier import (
            HUMAN_SECTION_HEADING,
            SYSTEM_SECTION_HEADING,
            PromptTemplate,
        )

        content = (
            f"{SYSTEM_SECTION_HEADING}\n"
            "{{taxonomy_menu}}\n"
            f"{HUMAN_SECTION_HEADING}\n"
            "{{document_content}}\n"
        )
        tpl = self._make_template_with_content(content)
        assert isinstance(tpl, PromptTemplate)
        system_text, human_text = tpl.render_messages(
            taxonomy_menu="MENU", document_content="DOC"
        )
        assert "MENU" in system_text
        assert "DOC" in human_text

    def test_neither_heading_succeeds_as_single_section(self) -> None:
        from drover.classifier import PromptTemplate

        content = "flat template {taxonomy_menu} {document_content}"
        tpl = self._make_template_with_content(content)
        assert isinstance(tpl, PromptTemplate)
        system_text, human_text = tpl.render_messages(
            taxonomy_menu="MENU", document_content="DOC"
        )
        assert system_text == ""
        assert "MENU" in human_text
        assert "DOC" in human_text
