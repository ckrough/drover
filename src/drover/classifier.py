"""LLM-based document classifier.

Integrates with LangChain to classify documents using various AI providers
(OpenAI, Anthropic, Ollama) with structured output support.

Uses LangChain's `with_structured_output()` for reliable JSON extraction,
with fallback parsing for edge cases.
"""

import json
import os
import re
import socket
from collections.abc import Callable
from importlib.resources import files
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Any, cast

import yaml
from json_repair import repair_json
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_core.runnables import Runnable
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import ValidationError
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from drover.config import AIProvider, TaxonomyMode
from drover.logging import get_logger
from drover.metrics import create_metrics_callback
from drover.models import RawClassification
from drover.taxonomy.base import BaseTaxonomy

logger = get_logger(__name__)

# Exceptions that should trigger a retry (transient network failures).
# These are specific exceptions that indicate the request can be retried:
# - ConnectionError: Base class for connection issues (includes Reset, Refused, Aborted)
# - TimeoutError: Request exceeded time limit
# - socket.timeout: TCP-level socket timeout
# - ConnectionResetError: Server dropped the connection (errno 104)
# - ConnectionRefusedError: Server not accepting connections (errno 111)
# - BrokenPipeError: Writing to a closed connection (errno 32)
#
# Note: We explicitly avoid broad OSError which would catch non-retryable errors
# like PermissionError, FileNotFoundError, or "disk full" (errno 28).
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    socket.timeout,
    ConnectionResetError,
    ConnectionRefusedError,
    BrokenPipeError,
)


class ClassificationError(Exception):
    """Raised when classification fails.

    Attributes:
        debug_info: Optional dict containing prompt and response for debugging.
    """

    def __init__(
        self,
        message: str,
        debug_info: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.debug_info = debug_info


class LLMParseError(ClassificationError):
    """Raised when LLM output cannot be parsed."""

    pass


class TaxonomyValidationError(ClassificationError):
    """Raised when classification fails taxonomy validation in strict mode."""

    pass


class TemplateError(ClassificationError):
    """Raised when prompt template loading or validation fails."""

    pass


# Required placeholders that must be present in prompt templates
REQUIRED_PLACEHOLDERS = {"{taxonomy_menu}", "{document_content}"}


class PromptTemplate:
    """Loads and renders prompt templates from Markdown files."""

    def __init__(self, template_path: Path | None = None) -> None:
        """Initialize prompt template.

        Args:
            template_path: Path to template file, or None to use default.
        """
        self._resource_path: Traversable | None = None
        if template_path is None:
            self._resource_path = files("drover.prompts").joinpath("classification.md")
            self.template_path: Path | None = None
        else:
            self.template_path = template_path

        self._content: str | None = None
        self._frontmatter: dict[str, Any] | None = None

    def _load(self) -> None:
        """Load and parse template file.

        Raises:
            TemplateError: If file cannot be read or parsed.
        """
        if self._content is not None:
            return

        # Determine which source to read from
        if self._resource_path is not None:
            source_desc = str(self._resource_path)
        elif self.template_path is not None:
            source_desc = str(self.template_path)
        else:
            raise TemplateError("No template path configured")

        try:
            if self._resource_path is not None:
                raw = self._resource_path.read_text(encoding="utf-8")
            else:
                # self.template_path is guaranteed non-None here
                raw = self.template_path.read_text(encoding="utf-8")  # type: ignore[union-attr]
        except FileNotFoundError:
            raise TemplateError(f"Template file not found: {source_desc}")
        except PermissionError:
            raise TemplateError(f"Permission denied reading template: {source_desc}")
        except UnicodeDecodeError as e:
            raise TemplateError(f"Template encoding error (expected UTF-8): {e}")
        except OSError as e:
            raise TemplateError(f"Failed to read template file: {e}")

        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                try:
                    self._frontmatter = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError as e:
                    raise TemplateError(f"Invalid YAML frontmatter: {e}")
                self._content = parts[2].strip()
            else:
                self._frontmatter = {}
                self._content = raw
        else:
            self._frontmatter = {}
            self._content = raw

        self._validate_placeholders()

    @property
    def content(self) -> str:
        """Get template content (without frontmatter)."""
        self._load()
        return self._content or ""

    @property
    def frontmatter(self) -> dict[str, Any]:
        """Get template frontmatter metadata."""
        self._load()
        return self._frontmatter or {}

    def render(self, **kwargs: Any) -> str:
        """Render template with provided variables.

        Args:
            **kwargs: Variables to substitute in template.

        Returns:
            Rendered template string.
        """
        content = self.content
        for key, value in kwargs.items():
            content = content.replace(f"{{{key}}}", str(value))
        return content

    def _validate_placeholders(self) -> None:
        """Validate that required placeholders are present.

        Raises:
            TemplateError: If required placeholders are missing.
        """
        content = self._content or ""
        missing = [p for p in REQUIRED_PLACEHOLDERS if p not in content]
        if missing:
            raise TemplateError(
                f"Template missing required placeholders: {', '.join(sorted(missing))}"
            )


class DocumentClassifier:
    """Classifies documents using LLM with taxonomy constraints.

    Handles provider abstraction, prompt rendering, structured output
    parsing, and taxonomy normalization.
    """

    def __init__(
        self,
        provider: AIProvider,
        model: str,
        taxonomy: BaseTaxonomy,
        taxonomy_mode: TaxonomyMode = TaxonomyMode.FALLBACK,
        template_path: Path | None = None,
        temperature: float = 0.1,
        max_tokens: int | None = 1000,
        timeout: int = 60,
        max_retries: int = 3,
        retry_min_wait: float = 2.0,
        retry_max_wait: float = 10.0,
    ) -> None:
        """Initialize classifier.

        Args:
            provider: AI provider (ollama, openai, anthropic).
            model: Model name/identifier.
            taxonomy: Taxonomy for classification constraints.
            taxonomy_mode: How to handle unknown values (strict/fallback).
            template_path: Custom prompt template path.
            temperature: LLM temperature (0.0 for deterministic output).
            max_tokens: Maximum tokens in response.
            timeout: Request timeout in seconds.
            max_retries: Maximum retry attempts for transient failures.
            retry_min_wait: Minimum wait between retries in seconds.
            retry_max_wait: Maximum wait between retries in seconds.
        """
        self.provider = provider
        self.model = model
        self.taxonomy = taxonomy
        self.taxonomy_mode = taxonomy_mode
        self.template = PromptTemplate(template_path)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_min_wait = retry_min_wait
        self.retry_max_wait = retry_max_wait
        self._llm: BaseChatModel | None = None
        self._structured_llm: Runnable[Any, Any] | None = None

    def _get_llm(self) -> BaseChatModel:
        """Get or create base LLM instance.

        Note: This returns the base LLM without structured output wrapping.
        Use _get_structured_llm() for classification with automatic parsing.
        """
        if self._llm is not None:
            return self._llm

        match self.provider:
            case AIProvider.OLLAMA:
                # LangChain stubs don't include timeout parameter
                self._llm = ChatOllama(
                    model=self.model,
                    temperature=self.temperature,
                    num_predict=self.max_tokens,
                    timeout=self.timeout,  # type: ignore[call-arg]
                )
            case AIProvider.OPENAI:
                # LangChain stubs don't include max_tokens but it works at runtime
                self._llm = ChatOpenAI(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,  # type: ignore[call-arg]
                    timeout=self.timeout,
                )
            case AIProvider.ANTHROPIC:
                from langchain_anthropic import ChatAnthropic

                # Enable prompt caching beta for cost optimization
                # The taxonomy menu is ~2000 tokens and identical across all
                # documents, making it ideal for caching (up to 90% cost reduction)
                # LangChain stubs don't include model/max_tokens/extra_headers
                self._llm = ChatAnthropic(  # type: ignore[call-arg]
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=float(self.timeout),
                    extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
                )
            case AIProvider.OPENROUTER:
                # OpenRouter needs explicit API key since we override base_url;
                # LangChain only auto-reads OPENAI_API_KEY for default endpoints
                api_key = os.environ.get("OPENROUTER_API_KEY")
                if not api_key:
                    raise ValueError(
                        "OPENROUTER_API_KEY environment variable must be set "
                        "when using the 'openrouter' provider"
                    )
                # LangChain stubs don't include max_tokens
                self._llm = ChatOpenAI(
                    model=self.model,
                    base_url="https://openrouter.ai/api/v1",
                    api_key=api_key,  # type: ignore[arg-type]
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,  # type: ignore[call-arg]
                    timeout=self.timeout,
                )
            case _:
                raise ValueError(f"Unsupported provider: {self.provider}")

        return self._llm

    def _get_structured_llm(self) -> Runnable[Any, Any]:
        """Get LLM with structured output for RawClassification schema.

        Uses LangChain's with_structured_output() for reliable JSON extraction.
        This eliminates the need for manual JSON parsing in most cases.

        The structured output method varies by provider:
        - OpenAI: Uses json_schema mode for strict schema adherence
        - Anthropic: Uses tool calling under the hood
        - Ollama: Uses JSON mode with schema validation

        Returns:
            Runnable that outputs RawClassification directly on success,
            or raises an error on parsing failure.
        """
        if self._structured_llm is not None:
            return self._structured_llm

        llm = self._get_llm()

        # Configure structured output based on provider capabilities
        match self.provider:
            case AIProvider.OPENAI | AIProvider.OPENROUTER:
                # OpenAI supports strict JSON schema mode
                self._structured_llm = llm.with_structured_output(
                    RawClassification,
                    method="json_schema",
                    strict=True,
                    include_raw=True,  # Include raw response for debugging
                )
            case AIProvider.ANTHROPIC:
                # Anthropic uses tool calling for structured output
                self._structured_llm = llm.with_structured_output(
                    RawClassification,
                    include_raw=True,
                )
            case AIProvider.OLLAMA:
                # Ollama uses JSON mode with schema
                self._structured_llm = llm.with_structured_output(
                    RawClassification,
                    include_raw=True,
                )
            case _:
                raise ValueError(f"Unsupported provider: {self.provider}")

        return self._structured_llm

    def _make_retry_decorator(self) -> Callable[..., Any]:
        """Create a retry decorator with configured parameters."""
        return retry(
            stop=stop_after_attempt(self.max_retries),
            wait=wait_exponential(
                multiplier=1,
                min=self.retry_min_wait,
                max=self.retry_max_wait,
            ),
            retry=retry_if_exception_type(RETRYABLE_EXCEPTIONS),
            reraise=True,
        )

    async def _invoke_structured_with_retry(
        self,
        message: HumanMessage,
        config: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """Invoke structured LLM with retry logic for transient failures.

        Uses LangChain's with_structured_output() for reliable parsing.

        Args:
            message: The message to send to the LLM.
            config: Optional invoke config (e.g., callbacks).

        Returns:
            Dict with keys 'raw', 'parsed', and 'parsing_error' from
            structured output with include_raw=True.

        Raises:
            Original exception after max retries exhausted.
        """
        structured_llm = self._get_structured_llm()

        @self._make_retry_decorator()
        async def _invoke() -> dict[str, Any]:
            if config is not None:
                result = await structured_llm.ainvoke(
                    [message],
                    config=config,  # type: ignore[arg-type]
                )
            else:
                result = await structured_llm.ainvoke([message])
            # Result is a dict-like object from LangChain structured output
            return cast(dict[str, Any], result)

        return cast(dict[str, Any], await _invoke())

    async def _invoke_with_retry(
        self,
        message: HumanMessage,
        config: dict[str, Any] | None,
    ) -> str:
        """Invoke base LLM with retry logic for transient failures.

        This is the fallback method that returns raw string response.
        Prefer _invoke_structured_with_retry() for classification.

        Args:
            message: The message to send to the LLM.
            config: Optional invoke config (e.g., callbacks).

        Returns:
            The LLM response content as string.

        Raises:
            Original exception after max retries exhausted.
        """
        llm = self._get_llm()

        @self._make_retry_decorator()
        async def _invoke() -> str:
            if config is not None:
                response = await llm.ainvoke(
                    [message],
                    config=config,  # type: ignore[arg-type]
                )
            else:
                response = await llm.ainvoke([message])
            return str(response.content)

        return cast(str, await _invoke())

    async def classify(
        self,
        content: str,
        capture_debug: bool = False,
        collect_metrics: bool = False,
    ) -> tuple[RawClassification, dict[str, Any] | None]:
        """Classify document content using structured output.

        Uses LangChain's with_structured_output() for reliable JSON extraction,
        with fallback to manual parsing for edge cases.

        Args:
            content: Extracted document text content.
            capture_debug: Whether to capture debug info (prompt, response).
            collect_metrics: Whether to collect AI metrics for this call.

        Returns:
            Tuple of (classification result, debug info dict or None).

        Raises:
            LLMParseError: If LLM output cannot be parsed.
            TaxonomyValidationError: If strict mode validation fails.
        """
        logger.info(
            "classification_started",
            provider=self.provider.value,
            model=self.model,
            content_length=len(content),
        )

        taxonomy_menu = self.taxonomy.to_prompt_menu()
        prompt = self.template.render(
            taxonomy_menu=taxonomy_menu,
            document_content=content,
        )

        debug_info: dict[str, Any] | None = None
        if capture_debug or collect_metrics:
            debug_info = {}
            if capture_debug:
                debug_info["prompt"] = prompt

        metrics_callback = None
        if collect_metrics:
            metrics_callback = create_metrics_callback(self.provider.value, self.model)

        message = HumanMessage(content=prompt)

        # In LangChain 0.3+ callbacks should be passed via the runnable config
        invoke_config: dict[str, Any] | None = None
        if metrics_callback is not None:
            invoke_config = {"callbacks": [metrics_callback]}

        # Try structured output first (modern LangChain pattern)
        result = await self._invoke_structured_with_retry(message, invoke_config)

        # Extract raw response for debugging
        raw_message = result.get("raw")
        raw_response = str(raw_message.content) if raw_message else None

        if capture_debug and debug_info is not None:
            debug_info["response"] = raw_response
        if collect_metrics and metrics_callback is not None and debug_info is not None:
            debug_info["metrics"] = metrics_callback.metrics.model_dump()

        # Check if structured parsing succeeded
        parsed = result.get("parsed")
        parsing_error = result.get("parsing_error")

        if parsed is not None and parsing_error is None:
            # Structured output succeeded - use the parsed RawClassification
            logger.debug(
                "structured_output_success",
                provider=self.provider.value,
                model=self.model,
            )
            classification = parsed
        else:
            # Structured output failed - fall back to manual parsing
            logger.warning(
                "structured_output_fallback",
                provider=self.provider.value,
                model=self.model,
                error=str(parsing_error) if parsing_error else "No parsed result",
            )
            if raw_response is None:
                raise LLMParseError(
                    "Structured output failed and no raw response available",
                    debug_info=debug_info,
                )
            try:
                classification_dict = self._parse_response(raw_response)
                classification = RawClassification.model_validate(classification_dict)
            except ClassificationError as e:
                # Re-raise with debug_info attached
                raise type(e)(str(e), debug_info=debug_info) from e

        # Normalize through taxonomy - wrap to preserve debug_info on failure
        try:
            normalized = self._normalize_classification(classification)
        except ClassificationError as e:
            raise type(e)(str(e), debug_info=debug_info) from e

        logger.info(
            "classification_complete",
            domain=normalized.domain,
            category=normalized.category,
            doctype=normalized.doctype,
            provider=self.provider.value,
            model=self.model,
        )

        return normalized, debug_info

    async def classify_streaming(
        self,
        content: str,
        on_token: Callable[[str], None] | None = None,
    ) -> RawClassification:
        """Classify document content with streaming output.

        Streams tokens as they arrive from the LLM, providing real-time
        feedback for interactive use. Falls back to manual parsing since
        structured output doesn't support streaming.

        Args:
            content: Extracted document text content.
            on_token: Optional callback invoked for each token received.
                     Useful for real-time display in CLI or UI.

        Returns:
            Normalized RawClassification result.

        Raises:
            LLMParseError: If LLM output cannot be parsed.
            TaxonomyValidationError: If strict mode validation fails.
        """
        logger.info(
            "classification_streaming_started",
            provider=self.provider.value,
            model=self.model,
            content_length=len(content),
        )

        taxonomy_menu = self.taxonomy.to_prompt_menu()
        prompt = self.template.render(
            taxonomy_menu=taxonomy_menu,
            document_content=content,
        )

        message = HumanMessage(content=prompt)
        llm = self._get_llm()

        # Collect streamed tokens
        chunks: list[str] = []

        async for chunk in llm.astream([message]):
            token = str(chunk.content)
            chunks.append(token)
            if on_token is not None:
                on_token(token)

        full_response = "".join(chunks)

        # Parse the accumulated response
        classification_dict = self._parse_response(full_response)
        classification = RawClassification.model_validate(classification_dict)

        # Normalize through taxonomy
        normalized = self._normalize_classification(classification)

        logger.info(
            "classification_streaming_complete",
            domain=normalized.domain,
            category=normalized.category,
            doctype=normalized.doctype,
            provider=self.provider.value,
            model=self.model,
        )

        return normalized

    def _parse_response(self, response: str) -> dict[str, Any]:
        """Parse LLM response as JSON with field validation.

        Uses json-repair library for robust handling of malformed JSON from LLMs.

        Args:
            response: Raw LLM response text.

        Returns:
            Parsed JSON dictionary with all required fields.

        Raises:
            LLMParseError: If JSON parsing fails or required fields missing.
        """
        response = response.strip()

        # Handle chain-of-thought format with <classification_analysis> tags
        # The JSON object follows the closing tag
        close_tag = "</classification_analysis>"
        if close_tag in response:
            response = response.split(close_tag, 1)[1].strip()

        parsed = None

        # Try direct JSON parsing first (fastest path)
        try:
            parsed = json.loads(response)
        except json.JSONDecodeError:
            pass

        # Handle template-style double-brace wrappers like `{{ ... }}`
        if parsed is None and response.startswith("{{") and response.endswith("}}"):
            candidate = "{" + response[2:-2].strip() + "}"
            try:
                parsed = json.loads(candidate)
            except json.JSONDecodeError:
                response = candidate

        # Try extracting JSON from markdown code blocks
        if parsed is None:
            code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if code_match:
                block = code_match.group(1).strip()
                try:
                    parsed = json.loads(block)
                except json.JSONDecodeError:
                    # Try json-repair on the code block
                    try:
                        repaired = repair_json(block, return_objects=True)
                        if isinstance(repaired, dict):
                            parsed = repaired
                    except Exception:
                        pass

        # Use json-repair as final fallback - handles malformed JSON,
        # surrounding text, trailing commas, unquoted keys, etc.
        if parsed is None:
            try:
                repaired = repair_json(response, return_objects=True)
                if isinstance(repaired, dict):
                    parsed = repaired
            except Exception:
                pass

        if parsed is None:
            raise LLMParseError(f"Could not parse JSON from response: {response[:200]}...")

        # Validate required fields
        required_fields = {"domain", "category", "doctype", "vendor", "date", "subject"}
        missing = required_fields - set(parsed.keys())
        if missing:
            raise LLMParseError(f"LLM response missing required fields: {missing}")

        # Validate field types
        for field in required_fields:
            if not isinstance(parsed[field], str):
                raise LLMParseError(
                    f"Field '{field}' must be string, got {type(parsed[field]).__name__}"
                )

        return cast(dict[str, Any], parsed)

    def _normalize_classification(
        self, raw: dict[str, Any] | RawClassification
    ) -> RawClassification:
        """Normalize classification through taxonomy.

        Args:
            raw: Raw classification dict or RawClassification from LLM.
                 Accepts both for compatibility with structured output
                 (returns RawClassification) and fallback parsing (returns dict).

        Returns:
            Normalized RawClassification.

        Raises:
            TaxonomyValidationError: If strict mode and unknown value found.
        """
        # Accept either dict or RawClassification for flexibility
        if isinstance(raw, RawClassification):
            classification = raw
        else:
            try:
                classification = RawClassification.model_validate(raw)
            except ValidationError as e:
                raise LLMParseError(f"Invalid classification structure: {e}")

        normalized_domain = self.taxonomy.canonical_domain(classification.domain)
        if normalized_domain is None:
            if self.taxonomy_mode == TaxonomyMode.STRICT:
                raise TaxonomyValidationError(
                    f"Unknown domain '{classification.domain}' not in taxonomy"
                )
            normalized_domain = "other"

        normalized_category = self.taxonomy.canonical_category(
            normalized_domain, classification.category
        )
        if normalized_category is None:
            if self.taxonomy_mode == TaxonomyMode.STRICT:
                raise TaxonomyValidationError(
                    f"Unknown category '{classification.category}' for domain '{normalized_domain}'"
                )
            normalized_category = "other"

        normalized_doctype = self.taxonomy.canonical_doctype(classification.doctype)
        if normalized_doctype is None:
            if self.taxonomy_mode == TaxonomyMode.STRICT:
                raise TaxonomyValidationError(
                    f"Unknown doctype '{classification.doctype}' not in taxonomy"
                )
            normalized_doctype = "other"

        return RawClassification(
            domain=normalized_domain,
            category=normalized_category,
            doctype=normalized_doctype,
            vendor=classification.vendor,
            date=classification.date,
            subject=classification.subject,
        )
