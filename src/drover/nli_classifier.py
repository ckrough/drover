"""Zero-shot NLI document classifier using DeBERTa-v3.

This module provides an alternative to generative LLM classification
using Natural Language Inference. Documents are classified by scoring
entailment between document text and label hypotheses.

Example:
    Document: "Bank of America statement showing balance..."
    Hypothesis: "This document belongs to the financial domain."
    Score: 0.92 (high entailment) -> Classified as "financial"

Requires optional dependencies: pip install drover[nli]
"""

from __future__ import annotations

import asyncio
import functools
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from drover.aggregation import AGGREGATORS
from drover.chunking import CHUNKERS
from drover.config import Aggregation, AIProvider, ChunkStrategy, TaxonomyMode
from drover.extractors.regex import RegexExtractor
from drover.logging import get_logger
from drover.models import RawClassification

if TYPE_CHECKING:
    from collections.abc import Callable

    from drover.extractors.base import BaseExtractor
    from drover.taxonomy.base import BaseTaxonomy


logger = get_logger(__name__)


class NLIImportError(ImportError):
    """Raised when NLI dependencies are not installed."""

    def __init__(self) -> None:
        super().__init__(
            "NLI dependencies not installed. Install with: pip install drover[nli]"
        )


class NLIClassificationError(Exception):
    """Base exception for NLI classification errors."""

    def __init__(self, message: str, debug_info: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.debug_info = debug_info or {}


class TaxonomyValidationError(NLIClassificationError):
    """Raised when classification fails taxonomy validation in strict mode."""


# Hypothesis templates for each classification level
DOMAIN_TEMPLATES = [
    "This document belongs to the {label} domain.",
    "This is a {label} document.",
]

CATEGORY_TEMPLATES = [
    "This {domain} document is related to {label}.",
    "The category of this {domain} document is {label}.",
]

DOCTYPE_TEMPLATES = [
    "This document is a {label}.",
    "The document type is {label}.",
]


def _label_to_readable(label: str) -> str:
    """Convert underscore-separated label to readable form.

    Example: "financial_aid" -> "financial aid"
    """
    return label.replace("_", " ")


def generate_domain_hypotheses(taxonomy: BaseTaxonomy) -> dict[str, list[str]]:
    """Generate hypothesis sentences for each domain.

    Args:
        taxonomy: Taxonomy providing canonical domain list.

    Returns:
        Dict mapping domain names to list of hypothesis strings.
    """
    hypotheses = {}
    for domain in taxonomy.all_domains():
        readable = _label_to_readable(domain)
        hypotheses[domain] = [
            template.format(label=readable) for template in DOMAIN_TEMPLATES
        ]
    return hypotheses


def generate_category_hypotheses(
    taxonomy: BaseTaxonomy, domain: str
) -> dict[str, list[str]]:
    """Generate hypothesis sentences for categories within a domain.

    Args:
        taxonomy: Taxonomy providing category list.
        domain: The domain to get categories for.

    Returns:
        Dict mapping category names to list of hypothesis strings.
    """
    hypotheses = {}
    domain_readable = _label_to_readable(domain)
    for category in taxonomy.categories_for_domain(domain):
        readable = _label_to_readable(category)
        hypotheses[category] = [
            template.format(domain=domain_readable, label=readable)
            for template in CATEGORY_TEMPLATES
        ]
    return hypotheses


def generate_doctype_hypotheses(taxonomy: BaseTaxonomy) -> dict[str, list[str]]:
    """Generate hypothesis sentences for document types.

    Args:
        taxonomy: Taxonomy providing doctype list.

    Returns:
        Dict mapping doctype names to list of hypothesis strings.
    """
    hypotheses = {}
    for doctype in taxonomy.all_doctypes():
        readable = _label_to_readable(doctype)
        hypotheses[doctype] = [
            template.format(label=readable) for template in DOCTYPE_TEMPLATES
        ]
    return hypotheses


@dataclass
class NLIDocumentClassifier:
    """Zero-shot NLI-based document classifier.

    Uses a cross-encoder NLI model (DeBERTa-v3) to classify documents
    by scoring entailment between document text and label hypotheses.
    This approach requires no fine-tuning and runs locally.

    Attributes:
        taxonomy: Taxonomy for classification labels and normalization.
        taxonomy_mode: STRICT (fail on unknown) or FALLBACK (map to "other").
        extractor: Extractor for vendor/date/subject fields.
        model_name: HuggingFace model identifier.
        device: Compute device (cuda, mps, cpu, or None for auto).
        max_tokens: Maximum tokens for model input (DeBERTa limit is 512).
    """

    taxonomy: BaseTaxonomy
    taxonomy_mode: TaxonomyMode = TaxonomyMode.FALLBACK
    extractor: BaseExtractor = field(default_factory=RegexExtractor)
    model_name: str = "cross-encoder/nli-deberta-v3-base"
    device: str | None = None
    max_tokens: int = 450  # Reserve ~62 tokens for hypothesis + special tokens

    # Phase 2 chunking + aggregation. Defaults preserve Phase 1 behavior
    # (single truncated chunk, max-pool across hypothesis templates).
    chunk_strategy: ChunkStrategy = ChunkStrategy.TRUNCATE
    chunk_size: int = 400
    chunk_overlap: int = 100
    aggregation: Aggregation = Aggregation.MAX

    # Interface parity with DocumentClassifier (used by evaluation framework).
    provider: AIProvider = AIProvider.NLI_LOCAL

    # Internal state (lazy-loaded)
    _tokenizer: Any = field(default=None, repr=False)
    _model: Any = field(default=None, repr=False)
    _torch: Any = field(default=None, repr=False)

    @property
    def model(self) -> str:
        """Alias for `model_name`, for parity with DocumentClassifier."""
        return self.model_name

    def __post_init__(self) -> None:
        """Validate configuration."""
        if self.max_tokens > 450:
            logger.warning(
                "max_tokens > 450 may cause truncation issues with hypotheses"
            )

    def _ensure_dependencies(self) -> None:
        """Lazily import and verify NLI dependencies."""
        if self._torch is not None:
            return

        try:
            import torch
            from transformers import AutoModelForSequenceClassification, AutoTokenizer

            self._torch = torch
            self._auto_model_cls = AutoModelForSequenceClassification
            self._auto_tokenizer_cls = AutoTokenizer
        except ImportError as e:
            raise NLIImportError() from e

    def _get_device(self) -> str:
        """Detect or validate compute device."""
        self._ensure_dependencies()
        torch = self._torch

        if self.device is not None:
            return self.device

        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        return "cpu"

    def _get_model(self) -> tuple[Any, Any]:
        """Lazy-load tokenizer and model.

        Returns:
            Tuple of (tokenizer, model).
        """
        if self._model is not None:
            return self._tokenizer, self._model

        self._ensure_dependencies()

        logger.info("loading_nli_model", model=self.model_name)

        device = self._get_device()
        self._tokenizer = self._auto_tokenizer_cls.from_pretrained(self.model_name)
        self._model = self._auto_model_cls.from_pretrained(self.model_name)
        self._model = self._model.to(device)

        # Set model to inference mode
        self._model.train(False)

        logger.info("nli_model_loaded", device=device)

        return self._tokenizer, self._model

    def _truncate_content(self, content: str) -> str:
        """Truncate content to fit within token limit.

        Args:
            content: Document text content.

        Returns:
            Truncated content string.
        """
        tokenizer, _ = self._get_model()

        tokens = tokenizer.encode(content, add_special_tokens=False)
        if len(tokens) <= self.max_tokens:
            return content

        truncated_tokens = tokens[: self.max_tokens]
        decoded: str = tokenizer.decode(truncated_tokens, skip_special_tokens=True)
        return decoded

    def _compute_entailment_score(self, premise: str, hypothesis: str) -> float:
        """Compute entailment probability for premise-hypothesis pair.

        Args:
            premise: Document text (possibly truncated).
            hypothesis: Label hypothesis to test.

        Returns:
            Entailment probability (0.0 to 1.0).
        """
        tokenizer, model = self._get_model()
        torch = self._torch
        device = self._get_device()

        inputs = tokenizer(
            premise,
            hypothesis,
            return_tensors="pt",
            truncation=True,
            max_length=512,
            padding=True,
        ).to(device)

        with torch.no_grad():
            outputs = model(**inputs)
            probs = torch.softmax(outputs.logits, dim=-1)
            # NLI models: 0=contradiction, 1=neutral, 2=entailment
            entailment_prob = probs[0, 2].item()

        return float(entailment_prob)

    def _classify_level(
        self,
        chunks: list[str],
        hypotheses: dict[str, list[str]],
    ) -> tuple[str, dict[str, float], list[dict[str, float]]]:
        """Classify chunks against a set of label hypotheses.

        For each label, computes one score per chunk by max-pooling across
        the hypothesis templates, then aggregates the per-chunk scores into
        one final label score using `self.aggregation`.

        Args:
            chunks: Document content split into chunks.
            hypotheses: Dict mapping labels to hypothesis strings.

        Returns:
            Tuple of (best_label, aggregated_scores, per_chunk_scores).
            `per_chunk_scores` is a list with one entry per chunk; each entry
            maps label -> max-template entailment score for that chunk.
        """
        aggregator = AGGREGATORS[self.aggregation]
        labels = list(hypotheses.keys())
        per_chunk: list[dict[str, float]] = [{} for _ in chunks]

        for label in labels:
            hypothesis_list = hypotheses[label]
            for chunk_idx, chunk in enumerate(chunks):
                template_scores = [
                    self._compute_entailment_score(chunk, h) for h in hypothesis_list
                ]
                per_chunk[chunk_idx][label] = max(template_scores)

        scores: dict[str, float] = {
            label: aggregator([per_chunk[i][label] for i in range(len(chunks))])
            for label in labels
        }

        best_label = max(scores, key=lambda k: scores[k])
        return best_label, scores, per_chunk

    def _get_chunks(self, content: str, docling_doc: Any | None = None) -> list[str]:
        """Split content into NLI-friendly chunks.

        When `docling_doc` is provided, a Docling `HybridChunker` walks the
        parsed document tree and emits chunks that respect both token
        budgets and structural boundaries (sections, tables). Each chunk is
        contextualized with its heading breadcrumb so the entailment
        cross-encoder sees section text as evidence. Otherwise, fall back
        to the configured `ChunkStrategy` token-window heuristic.
        """
        if docling_doc is not None:
            chunks = self._chunk_with_hybrid(docling_doc)
            if chunks:
                return chunks
            # An empty result from HybridChunker (degenerate doc) drops to
            # the flat-text path below rather than returning [].

        tokenizer, _ = self._get_model()
        chunker = CHUNKERS[self.chunk_strategy]

        if self.chunk_strategy == ChunkStrategy.TRUNCATE:
            return chunker(content, tokenizer, self.max_tokens)
        if self.chunk_strategy == ChunkStrategy.SLIDING:
            return chunker(content, tokenizer, self.chunk_size, self.chunk_overlap)
        # IMPORTANCE
        return chunker(content, tokenizer, self.chunk_size)

    def _build_hybrid_chunker(self) -> Any:
        """Construct a Docling `HybridChunker` aligned to the NLI tokenizer.

        Token budget matches `self.max_tokens` so chunks fit the same
        window the entailment cross-encoder will score, avoiding silent
        truncation between chunking and inference. Isolated for tests.
        """
        from docling.chunking import HybridChunker  # type: ignore[attr-defined]
        from docling_core.transforms.chunker.tokenizer.huggingface import (
            HuggingFaceTokenizer,
        )

        tokenizer = HuggingFaceTokenizer.from_pretrained(
            model_name=self.model_name,
            max_tokens=self.max_tokens,
        )
        return HybridChunker(tokenizer=tokenizer, merge_peers=True)

    def _chunk_with_hybrid(self, docling_doc: Any) -> list[str]:
        """Chunk a parsed `DoclingDocument` with `HybridChunker`.

        Returns `chunker.contextualize(chunk)` so each chunk carries its
        heading breadcrumb in the text the NLI model sees.
        """
        chunker = self._build_hybrid_chunker()
        return [
            chunker.contextualize(chunk) for chunk in chunker.chunk(dl_doc=docling_doc)
        ]

    def _classify_sync(
        self,
        content: str,
        capture_debug: bool = False,
        docling_doc: Any | None = None,
    ) -> tuple[RawClassification, dict[str, Any] | None]:
        """Synchronous classification implementation.

        This is the core classification logic, run in a thread for async.
        """
        # Chunk content according to the configured strategy.
        chunks = self._get_chunks(content, docling_doc=docling_doc)
        if not chunks:
            chunks = [""]

        # Hierarchical classification
        domain_hypotheses = generate_domain_hypotheses(self.taxonomy)
        domain, domain_scores, domain_chunk_scores = self._classify_level(
            chunks, domain_hypotheses
        )

        category_hypotheses = generate_category_hypotheses(self.taxonomy, domain)
        if category_hypotheses:
            category, category_scores, category_chunk_scores = self._classify_level(
                chunks, category_hypotheses
            )
        else:
            category = "other"
            category_scores = {}
            category_chunk_scores = []

        doctype_hypotheses = generate_doctype_hypotheses(self.taxonomy)
        doctype, doctype_scores, doctype_chunk_scores = self._classify_level(
            chunks, doctype_hypotheses
        )

        # Extract metadata fields
        extraction = self.extractor.extract(content)

        # Build raw classification
        raw = RawClassification(
            domain=domain,
            category=category,
            doctype=doctype,
            vendor=extraction.vendor,
            date=extraction.date,
            subject=extraction.subject,
        )

        # Normalize through taxonomy
        normalized = self._normalize_classification(raw)

        debug_info = None
        if capture_debug:
            debug_info = {
                "chunk_strategy": (
                    "hybrid" if docling_doc is not None else self.chunk_strategy.value
                ),
                "aggregation": self.aggregation.value,
                "chunk_count": len(chunks),
                "chunk_counts": {
                    "domain": len(chunks),
                    "category": len(chunks) if category_hypotheses else 0,
                    "doctype": len(chunks),
                },
                "chunk_scores": {
                    "domain": domain_chunk_scores,
                    "category": category_chunk_scores,
                    "doctype": doctype_chunk_scores,
                },
                "original_length": len(content),
                "domain_scores": domain_scores,
                "category_scores": category_scores,
                "doctype_scores": doctype_scores,
                "extraction": {
                    "vendor": extraction.vendor,
                    "date": extraction.date,
                    "subject": extraction.subject,
                },
            }

        logger.info(
            "nli_classification_complete",
            domain=normalized.domain,
            category=normalized.category,
            doctype=normalized.doctype,
            model=self.model_name,
        )

        return normalized, debug_info

    def _normalize_classification(self, raw: RawClassification) -> RawClassification:
        """Normalize classification through taxonomy.

        Args:
            raw: Raw classification from NLI scoring.

        Returns:
            Normalized RawClassification.

        Raises:
            TaxonomyValidationError: If strict mode and unknown value found.
        """
        normalized_domain = self.taxonomy.canonical_domain(raw.domain)
        if normalized_domain is None:
            if self.taxonomy_mode == TaxonomyMode.STRICT:
                raise TaxonomyValidationError(
                    f"Unknown domain '{raw.domain}' not in taxonomy"
                )
            normalized_domain = "other"

        normalized_category = self.taxonomy.canonical_category(
            normalized_domain, raw.category
        )
        if normalized_category is None:
            if self.taxonomy_mode == TaxonomyMode.STRICT:
                raise TaxonomyValidationError(
                    f"Unknown category '{raw.category}' for domain '{normalized_domain}'"
                )
            normalized_category = "other"

        normalized_doctype = self.taxonomy.canonical_doctype(raw.doctype)
        if normalized_doctype is None:
            if self.taxonomy_mode == TaxonomyMode.STRICT:
                raise TaxonomyValidationError(
                    f"Unknown doctype '{raw.doctype}' not in taxonomy"
                )
            normalized_doctype = "other"

        return RawClassification(
            domain=normalized_domain,
            category=normalized_category,
            doctype=normalized_doctype,
            vendor=raw.vendor,
            date=raw.date,
            subject=raw.subject,
        )

    async def classify(
        self,
        content: str,
        capture_debug: bool = False,
        collect_metrics: bool = False,  # noqa: ARG002 — kept for interface parity with DocumentClassifier
        docling_doc: Any | None = None,
    ) -> tuple[RawClassification, dict[str, Any] | None]:
        """Classify document using NLI entailment scoring.

        This method matches the signature of DocumentClassifier.classify()
        for drop-in compatibility. NLI inference is CPU-bound, so it runs
        in a thread pool to avoid blocking the event loop.

        Args:
            content: Extracted document text content.
            capture_debug: If True, include debug info in response.
            collect_metrics: Ignored (no API metrics for local model).
            docling_doc: Optional parsed `DoclingDocument`. When provided,
                chunking uses Docling's `HybridChunker` instead of the
                configured token-window strategy.

        Returns:
            Tuple of (RawClassification, optional debug info dict).

        Raises:
            NLIImportError: If transformers/torch not installed.
            TaxonomyValidationError: If strict mode and unknown value.
        """
        # Run CPU-bound inference in thread pool
        loop = asyncio.get_event_loop()
        classify_fn = functools.partial(
            self._classify_sync,
            content,
            capture_debug=capture_debug,
            docling_doc=docling_doc,
        )
        return await loop.run_in_executor(None, classify_fn)

    async def classify_streaming(
        self,
        content: str,
        on_token: Callable[[str], None] | None = None,
    ) -> RawClassification:
        """Classify with streaming output (compatibility method).

        NLI classification doesn't produce streaming tokens, but this
        method is provided for interface compatibility. The on_token
        callback is invoked once with the result summary.

        Args:
            content: Document text content.
            on_token: Optional callback (invoked once with summary).

        Returns:
            Normalized RawClassification.
        """
        result, _ = await self.classify(content)

        if on_token:
            summary = f"Domain: {result.domain}, Category: {result.category}, Type: {result.doctype}"
            on_token(summary)

        return result
