"""Tests for content-subject derivation in scripts/generate_eval_samples.py.

Covers the pure sanitizer that turns a model's free-text reply into a
convention-compliant ``subject`` (2-4 lowercase words describing content).
Guards prof-cgu: the generator must never again emit the document-type form
``f"{category} {doctype}"``.
"""

from __future__ import annotations

from typing import Any

import pytest

generate_eval_samples = pytest.importorskip("generate_eval_samples")
_sanitize_subject = generate_eval_samples._sanitize_subject
_fallback_subject = generate_eval_samples._fallback_subject
_subject_from_text = generate_eval_samples._subject_from_text
EmptyDocumentTextError = generate_eval_samples.EmptyDocumentTextError


def test_lowercases_and_trims() -> None:
    assert (
        _sanitize_subject("  Mortgage Refinance Offer  ") == "mortgage refinance offer"
    )


def test_strips_surrounding_quotes_and_trailing_period() -> None:
    assert _sanitize_subject('"account summary."') == "account summary"


def test_strips_period_glued_to_last_word() -> None:
    assert _sanitize_subject("renewal policy.") == "renewal policy"


def test_drops_leading_subject_label() -> None:
    assert _sanitize_subject("Subject: property tax notice") == "property tax notice"


def test_truncates_to_four_words() -> None:
    assert (
        _sanitize_subject("annual home insurance renewal policy declaration")
        == "annual home insurance renewal"
    )


def test_rejects_single_word() -> None:
    # One word cannot satisfy the 2-4 word convention; signal a retry.
    assert _sanitize_subject("invoice") is None


def test_rejects_empty() -> None:
    assert _sanitize_subject("   ") is None


def test_collapses_internal_whitespace_and_punctuation() -> None:
    assert _sanitize_subject("vehicle   loan,  agreement") == "vehicle loan agreement"


def test_fallback_returns_none_on_empty_text() -> None:
    # No content words -> caller decides how to surface the signal; the
    # fallback never silently writes a placeholder.
    assert _fallback_subject("") is None
    assert _fallback_subject("the and for this that") is None


def test_fallback_returns_first_content_words() -> None:
    assert _fallback_subject("Margaret Voss estate documents") == "margaret voss estate"


class _FakeClient:
    """Minimal stub for ``_call_anthropic_async``'s client argument."""

    def __init__(self, replies: list[str]) -> None:
        self._replies = list(replies)

    def take(self) -> str:
        return self._replies.pop(0)


async def _fake_call(
    client: _FakeClient, system: str, user: str
) -> tuple[str, dict[str, int]]:
    return client.take(), {
        "input_tokens": 10,
        "output_tokens": 3,
        "cache_read_tokens": 0,
        "cache_write_tokens": 0,
    }


@pytest.mark.asyncio
async def test_subject_from_text_retries_when_reply_matches_forbidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generate_eval_samples, "_call_anthropic_async", _fake_call)
    client = _FakeClient(["auto policy", "sedan collision coverage"])
    subject, _ = await _subject_from_text(
        client,  # type: ignore[arg-type]
        "Auto policy declarations and coverage details for a 2019 sedan.",
        forbidden="auto policy",
    )
    # First reply matches the forbidden category+doctype form, so the loop
    # must retry and accept the second reply.
    assert subject == "sedan collision coverage"


@pytest.mark.asyncio
async def test_subject_from_text_raises_on_empty_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(generate_eval_samples, "_call_anthropic_async", _fake_call)
    client = _FakeClient([])  # no calls should happen
    with pytest.raises(EmptyDocumentTextError):
        await _subject_from_text(client, "   \n   ")  # type: ignore[arg-type]


def _forbidden_form(obj: dict[str, Any]) -> str:
    """Mirror of backfill_eval_subjects._forbidden_form (avoid import dep)."""
    cat = str(obj.get("category", "")).replace("_", " ")
    dt = str(obj.get("doctype", "")).replace("_", " ")
    return f"{cat} {dt}".strip()


def test_forbidden_form_normalizes_underscores() -> None:
    assert _forbidden_form({"category": "financial_aid", "doctype": "agreements"}) == (
        "financial aid agreements"
    )
