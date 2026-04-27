"""Tests for the NLI chunking strategies (Phase 2)."""

from __future__ import annotations

from drover.chunking import (
    CHUNKERS,
    chunk_importance,
    chunk_sliding,
    chunk_truncate,
)
from drover.config import ChunkStrategy


class FakeTokenizer:
    """Whitespace tokenizer that mimics the AutoTokenizer interface used by chunkers.

    Words are tokens. encode() returns word indices into a per-call vocab; decode()
    joins back. This is sufficient for testing chunk boundaries without loading
    a real transformers model.
    """

    def encode(self, text: str, add_special_tokens: bool = False) -> list[int]:
        tokens = text.split()
        # Indices are positions in this call's vocab, not a global one;
        # decode below mirrors that convention.
        self._last_tokens = tokens
        return list(range(len(tokens)))

    def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
        return " ".join(self._last_tokens[i] for i in ids)


def _make_text(n_words: int) -> str:
    return " ".join(f"w{i}" for i in range(n_words))


class TestChunkTruncate:
    def test_returns_single_element(self) -> None:
        tok = FakeTokenizer()
        chunks = chunk_truncate(_make_text(50), tok, max_tokens=20)
        assert len(chunks) == 1

    def test_truncates_when_over_limit(self) -> None:
        tok = FakeTokenizer()
        chunks = chunk_truncate(_make_text(100), tok, max_tokens=10)
        assert len(chunks[0].split()) == 10

    def test_no_truncation_when_under_limit(self) -> None:
        tok = FakeTokenizer()
        chunks = chunk_truncate(_make_text(5), tok, max_tokens=20)
        assert chunks[0] == _make_text(5)

    def test_empty_returns_empty_list(self) -> None:
        tok = FakeTokenizer()
        assert chunk_truncate("", tok, max_tokens=20) == []


class TestChunkSliding:
    def test_short_input_single_chunk(self) -> None:
        tok = FakeTokenizer()
        chunks = chunk_sliding(_make_text(5), tok, chunk_size=20, overlap=5)
        assert len(chunks) == 1
        assert chunks[0] == _make_text(5)

    def test_long_input_multiple_overlapping_chunks(self) -> None:
        tok = FakeTokenizer()
        chunks = chunk_sliding(_make_text(100), tok, chunk_size=30, overlap=10)
        assert len(chunks) >= 4

        for chunk in chunks:
            assert len(chunk.split()) <= 30

    def test_chunks_cover_entire_input(self) -> None:
        """Concatenated unique-word coverage spans the full input."""
        tok = FakeTokenizer()
        text = _make_text(100)
        chunks = chunk_sliding(text, tok, chunk_size=30, overlap=10)

        seen: set[str] = set()
        for chunk in chunks:
            seen.update(chunk.split())
        assert seen == set(text.split())

    def test_overlap_creates_shared_words(self) -> None:
        tok = FakeTokenizer()
        chunks = chunk_sliding(_make_text(60), tok, chunk_size=30, overlap=10)

        first_words = set(chunks[0].split())
        second_words = set(chunks[1].split())
        shared = first_words & second_words
        assert len(shared) >= 5  # roughly the overlap

    def test_empty_returns_empty_list(self) -> None:
        tok = FakeTokenizer()
        assert chunk_sliding("", tok, chunk_size=20, overlap=5) == []


class TestChunkImportance:
    def test_returns_at_most_n_chunks(self) -> None:
        tok = FakeTokenizer()
        text = (
            "Bank statement for January. Account balance is positive. "
            "Transactions include groceries, fuel, and utilities. "
            "Interest accrued this month was minimal. "
            "Customer service can be reached at the listed number. "
            "This statement is system generated and requires no signature. "
            "Please review for accuracy and report discrepancies promptly."
        )
        chunks = chunk_importance(text, tok, chunk_size=20, n_chunks=3)
        assert 1 <= len(chunks) <= 3

    def test_each_chunk_fits_chunk_size(self) -> None:
        tok = FakeTokenizer()
        text = (
            "Sentence one with many words spans a decent length. "
            "Sentence two is also reasonably long and informative. "
            "Sentence three completes the trio and is similarly verbose."
        )
        chunks = chunk_importance(text, tok, chunk_size=15, n_chunks=3)

        for chunk in chunks:
            assert len(chunk.split()) <= 15

    def test_short_input_returns_input(self) -> None:
        """A document under chunk_size should round-trip as a single chunk."""
        tok = FakeTokenizer()
        text = "Short bank statement summary."
        chunks = chunk_importance(text, tok, chunk_size=50, n_chunks=3)
        assert len(chunks) == 1

    def test_empty_returns_empty_list(self) -> None:
        tok = FakeTokenizer()
        assert chunk_importance("", tok, chunk_size=20, n_chunks=3) == []


class TestChunkersRegistry:
    def test_registry_covers_all_strategies(self) -> None:
        for member in ChunkStrategy:
            assert member in CHUNKERS
            assert callable(CHUNKERS[member])
