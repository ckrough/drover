"""Chunking strategies for the NLI classifier (Phase 2).

A chunker takes raw document content plus a tokenizer and returns a list of
text chunks, each fitting within a token budget. The classifier scores each
chunk against every label hypothesis and aggregates the per-chunk scores.

The three strategies are:
- `chunk_truncate`: keep the first `max_tokens` tokens (Phase 1 behavior).
- `chunk_sliding`: overlapping windows covering the entire document.
- `chunk_importance`: pick the highest-TF-IDF-scoring sentences.

All chunkers return `[]` for empty input. The `Tokenizer` protocol matches
HuggingFace `AutoTokenizer` (encode/decode), so any tokenizer with that
interface works (real ones in production, fakes in tests).
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Protocol

from drover.config import ChunkStrategy

if TYPE_CHECKING:
    from collections.abc import Callable


class Tokenizer(Protocol):
    """Subset of the HuggingFace AutoTokenizer interface used by chunkers."""

    def encode(self, text: str, add_special_tokens: bool = ...) -> list[int]: ...

    def decode(self, ids: list[int], skip_special_tokens: bool = ...) -> str: ...


_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def chunk_truncate(content: str, tokenizer: Tokenizer, max_tokens: int) -> list[str]:
    """Return a single-element list with the first `max_tokens` tokens."""
    if not content:
        return []

    tokens = tokenizer.encode(content, add_special_tokens=False)
    if not tokens:
        return []

    if len(tokens) <= max_tokens:
        return [content]

    truncated = tokens[:max_tokens]
    return [tokenizer.decode(truncated, skip_special_tokens=True)]


def chunk_sliding(
    content: str, tokenizer: Tokenizer, chunk_size: int, overlap: int
) -> list[str]:
    """Split content into overlapping windows of `chunk_size` tokens.

    Each window steps forward by `chunk_size - overlap` tokens. The final
    window may be shorter than `chunk_size`. Together the windows cover the
    full input.
    """
    if not content:
        return []
    if overlap >= chunk_size:
        raise ValueError(
            f"overlap ({overlap}) must be less than chunk_size ({chunk_size})"
        )

    tokens = tokenizer.encode(content, add_special_tokens=False)
    if not tokens:
        return []

    if len(tokens) <= chunk_size:
        return [content]

    stride = chunk_size - overlap
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        window = tokens[start : start + chunk_size]
        if not window:
            break
        chunks.append(tokenizer.decode(window, skip_special_tokens=True))
        if start + chunk_size >= len(tokens):
            break
        start += stride

    return chunks


def chunk_importance(
    content: str,
    tokenizer: Tokenizer,
    chunk_size: int,
    n_chunks: int = 3,
) -> list[str]:
    """Pick the highest-TF-IDF-scoring sentences, packed into <= n_chunks chunks.

    For documents short enough to fit in `chunk_size` tokens, return the input
    unchanged as a single chunk. Otherwise, split into sentences, score with
    TF-IDF, and greedily pack the highest-scoring sentences into chunks.
    """
    if not content:
        return []

    tokens = tokenizer.encode(content, add_special_tokens=False)
    if not tokens:
        return []
    if len(tokens) <= chunk_size:
        return [content]

    sentences = [s.strip() for s in _SENTENCE_SPLIT.split(content) if s.strip()]
    if not sentences:
        return [tokenizer.decode(tokens[:chunk_size], skip_special_tokens=True)]

    scores = _tfidf_sentence_scores(sentences)
    ordered = sorted(
        zip(sentences, scores, strict=True),
        key=lambda pair: pair[1],
        reverse=True,
    )

    chunks: list[str] = []
    current_sentences: list[str] = []
    current_tokens = 0

    for sentence, _score in ordered:
        if len(chunks) >= n_chunks:
            break

        sentence_tokens = len(tokenizer.encode(sentence, add_special_tokens=False))

        if sentence_tokens > chunk_size:
            # Sentence alone exceeds chunk_size: hard-truncate it on its own.
            if current_sentences:
                chunks.append(" ".join(current_sentences))
                current_sentences = []
                current_tokens = 0
                if len(chunks) >= n_chunks:
                    break
            truncated_ids = tokenizer.encode(sentence, add_special_tokens=False)[
                :chunk_size
            ]
            chunks.append(tokenizer.decode(truncated_ids, skip_special_tokens=True))
            continue

        if current_tokens + sentence_tokens > chunk_size:
            chunks.append(" ".join(current_sentences))
            current_sentences = [sentence]
            current_tokens = sentence_tokens
        else:
            current_sentences.append(sentence)
            current_tokens += sentence_tokens

    if current_sentences and len(chunks) < n_chunks:
        chunks.append(" ".join(current_sentences))

    return chunks[:n_chunks]


def _tfidf_sentence_scores(sentences: list[str]) -> list[float]:
    """Return one score per sentence: sum of TF-IDF weights for its terms.

    Imports sklearn lazily so the [nli] extra is not required for callers that
    only use truncate/sliding chunking.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer

    vectorizer = TfidfVectorizer()
    matrix = vectorizer.fit_transform(sentences)
    # Sum across terms per row (sentence). Cast to plain floats.
    row_sums = matrix.sum(axis=1)
    return [float(row_sums[i, 0]) for i in range(len(sentences))]


CHUNKERS: dict[ChunkStrategy, Callable[..., list[str]]] = {
    ChunkStrategy.TRUNCATE: chunk_truncate,
    ChunkStrategy.SLIDING: chunk_sliding,
    ChunkStrategy.IMPORTANCE: chunk_importance,
}
