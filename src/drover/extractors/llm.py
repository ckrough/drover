"""Hybrid extractor combining regex with LLM fallback.

Uses regex patterns first for fast extraction, then falls back to
a small local LLM for fields that regex couldn't extract. This provides
a balance between speed and accuracy.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from drover.extractors.base import ExtractionResult, StructuredRegion
from drover.extractors.regex import RegexExtractor
from drover.logging import get_logger

if TYPE_CHECKING:
    from langchain_core.language_models import BaseChatModel


logger = get_logger(__name__)


# Minimal prompt for extraction - focuses on just the fields we need
EXTRACTION_PROMPT = """Extract the following from this document:
- vendor: The company or organization name (e.g., "Bank of America", "Verizon")
- date: The document date in YYYYMMDD format (e.g., "20240115")
- subject: A brief description of the document content (max 50 words)

Document excerpt:
{content}

Respond with JSON only, no explanation:
{{"vendor": "...", "date": "...", "subject": "..."}}"""


@dataclass
class HybridExtractor:
    """Hybrid extractor using regex with LLM fallback.

    First attempts extraction using fast regex patterns. For any fields
    that regex returns "unknown", falls back to a small LLM for semantic
    extraction.

    Attributes:
        llm: LangChain chat model for fallback extraction.
        regex_extractor: Regex extractor to try first.
        max_content_length: Max chars to send to LLM.
        timeout: LLM request timeout in seconds.
    """

    llm: BaseChatModel | None = None
    regex_extractor: RegexExtractor = field(default_factory=RegexExtractor)
    max_content_length: int = 2000
    timeout: int = 30

    def extract(
        self,
        content: str,
        structured_regions: list[StructuredRegion] | None = None,
    ) -> ExtractionResult:
        """Extract metadata using regex first, then LLM fallback.

        Args:
            content: Document text content.
            structured_regions: Optional typed regions (e.g., table rows)
                from a structure-aware loader. Forwarded to the inner
                regex extractor; the LLM fallback still operates on the
                truncated flat text.

        Returns:
            ExtractionResult with extracted values.
        """
        # First pass: regex extraction
        regex_result = self.regex_extractor.extract(
            content, structured_regions=structured_regions
        )

        # Check what needs LLM fallback
        needs_vendor = regex_result.vendor == "unknown"
        needs_date = regex_result.date == "unknown"
        needs_subject = regex_result.subject == "document"

        # If regex got everything, return immediately
        if not (needs_vendor or needs_date or needs_subject):
            logger.debug("regex_extraction_complete", all_fields_found=True)
            return regex_result

        # If no LLM configured, return regex results
        if self.llm is None:
            logger.debug(
                "llm_fallback_skipped",
                reason="no_llm_configured",
                missing_fields=[
                    f
                    for f, needed in [
                        ("vendor", needs_vendor),
                        ("date", needs_date),
                        ("subject", needs_subject),
                    ]
                    if needed
                ],
            )
            return regex_result

        # LLM fallback for missing fields
        try:
            llm_result = self._extract_with_llm(content)
            return self._merge_results(
                regex_result, llm_result, needs_vendor, needs_date, needs_subject
            )
        except Exception as e:
            logger.warning(
                "llm_extraction_failed",
                error=str(e),
                falling_back_to="regex_only",
            )
            return regex_result

    def _extract_with_llm(self, content: str) -> dict[str, str]:
        """Use LLM to extract metadata fields.

        Args:
            content: Document content.

        Returns:
            Dict with vendor, date, subject keys.
        """
        if self.llm is None:
            return {}

        # Truncate content for LLM
        truncated = content[: self.max_content_length]
        if len(content) > self.max_content_length:
            truncated += "\n[...truncated...]"

        prompt = EXTRACTION_PROMPT.format(content=truncated)

        logger.debug("llm_extraction_started")
        response = self.llm.invoke(prompt)
        raw_content = response.content if hasattr(response, "content") else response
        response_text = (
            raw_content if isinstance(raw_content, str) else str(raw_content)
        )

        # Parse JSON response
        result = self._parse_llm_response(response_text)
        logger.debug("llm_extraction_complete", result=result)

        return result

    def _parse_llm_response(self, response: str) -> dict[str, str]:
        """Parse LLM JSON response.

        Args:
            response: Raw LLM response text.

        Returns:
            Dict with extracted fields.
        """
        response = response.strip()

        # Try to extract JSON from response
        # Handle markdown code blocks
        if "```" in response:
            match = re.search(r"```(?:json)?\s*(.*?)\s*```", response, re.DOTALL)
            if match:
                response = match.group(1)

        # Handle responses that start with explanation
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            response = json_match.group(0)

        try:
            data = json.loads(response)
            return {
                "vendor": str(data.get("vendor", "unknown")),
                "date": self._normalize_date(str(data.get("date", "unknown"))),
                "subject": str(data.get("subject", "document")),
            }
        except json.JSONDecodeError:
            logger.warning("llm_json_parse_failed", response=response[:100])
            return {"vendor": "unknown", "date": "unknown", "subject": "document"}

    def _normalize_date(self, date_str: str) -> str:
        """Normalize date to YYYYMMDD format.

        Args:
            date_str: Date string from LLM.

        Returns:
            Normalized date or "unknown".
        """
        if date_str == "unknown" or not date_str:
            return "unknown"

        # Remove any non-alphanumeric characters
        cleaned = re.sub(r"[^0-9]", "", date_str)

        # If it's already 8 digits, assume YYYYMMDD
        if len(cleaned) == 8:
            return cleaned

        return "unknown"

    def _merge_results(
        self,
        regex_result: ExtractionResult,
        llm_result: dict[str, str],
        needs_vendor: bool,
        needs_date: bool,
        needs_subject: bool,
    ) -> ExtractionResult:
        """Merge regex and LLM results.

        Args:
            regex_result: Results from regex extraction.
            llm_result: Results from LLM extraction.
            needs_*: Flags indicating which fields needed LLM.

        Returns:
            Merged ExtractionResult.
        """
        vendor = (
            llm_result.get("vendor", "unknown") if needs_vendor else regex_result.vendor
        )
        date = llm_result.get("date", "unknown") if needs_date else regex_result.date
        subject = (
            llm_result.get("subject", "document")
            if needs_subject
            else regex_result.subject
        )

        # Track confidence (regex is high confidence, LLM is medium)
        confidence = {
            "vendor": 0.9 if not needs_vendor else 0.7,
            "date": 0.9 if not needs_date else 0.7,
            "subject": 0.9 if not needs_subject else 0.7,
        }

        return ExtractionResult(
            vendor=vendor if vendor != "unknown" else regex_result.vendor,
            date=date if date != "unknown" else regex_result.date,
            subject=subject if subject != "document" else regex_result.subject,
            confidence=confidence,
        )


def create_ollama_extractor(
    model: str = "phi3:mini",
    base_url: str = "http://localhost:11434",
) -> HybridExtractor:
    """Create a HybridExtractor with Ollama LLM fallback.

    Args:
        model: Ollama model name.
        base_url: Ollama server URL.

    Returns:
        Configured HybridExtractor.

    Raises:
        ImportError: If langchain-ollama not installed.
    """
    try:
        from langchain_ollama import ChatOllama
    except ImportError as e:
        raise ImportError(
            "langchain-ollama required for Ollama extraction. "
            "Install with: pip install langchain-ollama"
        ) from e

    llm = ChatOllama(
        model=model,
        base_url=base_url,
        temperature=0.0,
        num_predict=200,  # Short responses only
    )

    return HybridExtractor(llm=llm)
