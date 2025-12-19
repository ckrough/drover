"""Metadata extractors for document classification.

Extractors handle extraction of vendor, date, and subject fields
from document content. This is used by the NLI classifier which
can only classify but not extract free-form fields.
"""

from drover.extractors.base import BaseExtractor, ExtractionResult
from drover.extractors.llm import HybridExtractor, create_ollama_extractor
from drover.extractors.regex import RegexExtractor

__all__ = [
    "BaseExtractor",
    "ExtractionResult",
    "HybridExtractor",
    "RegexExtractor",
    "create_ollama_extractor",
]
