"""LLM-based document classifier.

Integrates with LangChain to classify documents using various AI providers
(OpenAI, Anthropic, Ollama) with structured output support.
"""

import json
import re
from collections.abc import Callable
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
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

# Exceptions that should trigger a retry (transient failures)
RETRYABLE_EXCEPTIONS = (
    ConnectionError,
    TimeoutError,
    OSError,  # Catches network-related OS errors
)


class ClassificationError(Exception):
    """Raised when classification fails."""

    pass


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
        if template_path is None:
            template_path = files("drover.prompts").joinpath("classification.md")

        self.template_path = template_path
        self._content: str | None = None
        self._frontmatter: dict | None = None

    def _load(self) -> None:
        """Load and parse template file.

        Raises:
            TemplateError: If file cannot be read or parsed.
        """
        if self._content is not None:
            return

        try:
            if hasattr(self.template_path, "read_text"):
                raw = self.template_path.read_text(encoding="utf-8")
            else:
                raw = Path(self.template_path).read_text(encoding="utf-8")
        except FileNotFoundError:
            raise TemplateError(f"Template file not found: {self.template_path}")
        except PermissionError:
            raise TemplateError(f"Permission denied reading template: {self.template_path}")
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
    def frontmatter(self) -> dict:
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

    def _get_llm(self) -> BaseChatModel:
        """Get or create LLM instance."""
        if self._llm is not None:
            return self._llm

        match self.provider:
            case AIProvider.OLLAMA:
                self._llm = ChatOllama(
                    model=self.model,
                    temperature=self.temperature,
                    num_predict=self.max_tokens,
                    format="json",
                    timeout=self.timeout,
                )
            case AIProvider.OPENAI:
                self._llm = ChatOpenAI(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=self.timeout,
                    model_kwargs={"response_format": {"type": "json_object"}},
                )
            case AIProvider.ANTHROPIC:
                from langchain_anthropic import ChatAnthropic

                self._llm = ChatAnthropic(
                    model=self.model,
                    temperature=self.temperature,
                    max_tokens=self.max_tokens,
                    timeout=float(self.timeout),
                )
            case _:
                raise ValueError(f"Unsupported provider: {self.provider}")

        return self._llm

    def _make_retry_decorator(self) -> Callable:
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

    async def _invoke_with_retry(
        self,
        message: HumanMessage,
        config: dict[str, Any] | None,
    ) -> str:
        """Invoke LLM with retry logic for transient failures.

        Args:
            message: The message to send to the LLM.
            config: Optional invoke config (e.g., callbacks).

        Returns:
            The LLM response content as string.

        Raises:
            Original exception after max retries exhausted.
        """
        llm = self._get_llm()

        # Apply retry decorator dynamically based on config
        @self._make_retry_decorator()
        async def _invoke():
            if config is not None:
                response = await llm.ainvoke([message], config=config)
            else:
                response = await llm.ainvoke([message])
            return str(response.content)

        return await _invoke()

    async def classify(
        self,
        content: str,
        capture_debug: bool = False,
        collect_metrics: bool = False,
    ) -> tuple[RawClassification, dict[str, Any] | None]:
        """Classify document content.

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

        # In LangChain 0.3+ callbacks should be passed via the runnable config,
        # not as a direct keyword argument, otherwise the internal
        # `agenerate_prompt` call can receive duplicate `callbacks` values.
        invoke_config: dict[str, Any] | None = None
        if metrics_callback is not None:
            invoke_config = {"callbacks": [metrics_callback]}

        raw_response = await self._invoke_with_retry(message, invoke_config)
        if capture_debug and debug_info is not None:
            debug_info["response"] = raw_response
        if collect_metrics and metrics_callback is not None and debug_info is not None:
            debug_info["metrics"] = metrics_callback.metrics.model_dump()

        classification = self._parse_response(raw_response)
        normalized = self._normalize_classification(classification)

        logger.info(
            "classification_complete",
            domain=normalized.domain,
            category=normalized.category,
            doctype=normalized.doctype,
            provider=self.provider.value,
            model=self.model,
        )

        return normalized, debug_info

    def _parse_response(self, response: str) -> dict:
        """Parse LLM response as JSON with field validation.

        Args:
            response: Raw LLM response text.

        Returns:
            Parsed JSON dictionary with all required fields.

        Raises:
            LLMParseError: If JSON parsing fails or required fields missing.
        """
        response = response.strip()
        parsed = None

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

        if parsed is None:
            code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
            if code_match:
                block = code_match.group(1).strip()
                try:
                    parsed = json.loads(block)
                except json.JSONDecodeError:
                    pass

        if parsed is None:
            candidate = self._extract_largest_json_object(response)
            if candidate is not None:
                try:
                    parsed = json.loads(candidate)
                except json.JSONDecodeError:
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

        return parsed

    def _extract_largest_json_object(self, text: str) -> str | None:
        """Extract the largest balanced JSON object substring from text.

        This uses a simple brace depth counter and is tolerant of
        surrounding non-JSON commentary.
        """
        best_span: tuple[int, int] | None = None
        depth = 0
        start_idx: int | None = None
        in_string = False
        escape = False

        for idx, ch in enumerate(text):
            if ch == '"' and not escape:
                in_string = not in_string
            if ch == "\\" and not escape:
                escape = True
            else:
                escape = False

            if in_string:
                continue

            if ch == "{":
                if depth == 0:
                    start_idx = idx
                depth += 1
            elif ch == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start_idx is not None:
                        end_idx = idx + 1
                        if best_span is None or (end_idx - start_idx) > (
                            best_span[1] - best_span[0]
                        ):
                            best_span = (start_idx, end_idx)

        if best_span is None:
            return None

        return text[best_span[0] : best_span[1]]

    def _normalize_classification(self, raw: dict) -> RawClassification:
        """Normalize classification through taxonomy.

        Args:
            raw: Raw classification dict from LLM.

        Returns:
            Normalized RawClassification.

        Raises:
            TaxonomyValidationError: If strict mode and unknown value found.
        """
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
