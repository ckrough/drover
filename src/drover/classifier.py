"""LLM-based document classifier.

Integrates with LangChain to classify documents using various AI providers
(OpenAI, Anthropic, Ollama) with structured output support.
"""

import json
import re
from importlib.resources import files
from pathlib import Path
from typing import Any

import yaml
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from pydantic import ValidationError

from drover.config import AIProvider, TaxonomyMode
from drover.models import RawClassification
from drover.taxonomy.base import BaseTaxonomy


class ClassificationError(Exception):
    """Raised when classification fails."""

    pass


class LLMParseError(ClassificationError):
    """Raised when LLM output cannot be parsed."""

    pass


class TaxonomyValidationError(ClassificationError):
    """Raised when classification fails taxonomy validation in strict mode."""

    pass


class PromptTemplate:
    """Loads and renders prompt templates from Markdown files."""

    def __init__(self, template_path: Path | None = None) -> None:
        """Initialize prompt template.

        Args:
            template_path: Path to template file, or None to use default.
        """
        if template_path is None:
            # Load default template from package resources
            template_path = files("drover.prompts").joinpath("classification.md")

        self.template_path = template_path
        self._content: str | None = None
        self._frontmatter: dict | None = None

    def _load(self) -> None:
        """Load and parse template file."""
        if self._content is not None:
            return

        if hasattr(self.template_path, "read_text"):
            # importlib.resources Traversable
            raw = self.template_path.read_text()
        else:
            raw = Path(self.template_path).read_text()

        # Parse YAML frontmatter
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                self._frontmatter = yaml.safe_load(parts[1]) or {}
                self._content = parts[2].strip()
            else:
                self._frontmatter = {}
                self._content = raw
        else:
            self._frontmatter = {}
            self._content = raw

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
    ) -> None:
        """Initialize classifier.

        Args:
            provider: AI provider (ollama, openai, anthropic).
            model: Model name/identifier.
            taxonomy: Taxonomy for classification constraints.
            taxonomy_mode: How to handle unknown values (strict/fallback).
            template_path: Custom prompt template path.
        """
        self.provider = provider
        self.model = model
        self.taxonomy = taxonomy
        self.taxonomy_mode = taxonomy_mode
        self.template = PromptTemplate(template_path)
        self._llm: BaseChatModel | None = None

    def _get_llm(self) -> BaseChatModel:
        """Get or create LLM instance."""
        if self._llm is not None:
            return self._llm

        match self.provider:
            case AIProvider.OLLAMA:
                self._llm = ChatOllama(model=self.model)
            case AIProvider.OPENAI:
                self._llm = ChatOpenAI(model=self.model)
            case AIProvider.ANTHROPIC:
                # langchain-anthropic import
                from langchain_anthropic import ChatAnthropic

                self._llm = ChatAnthropic(model=self.model)
            case _:
                raise ValueError(f"Unsupported provider: {self.provider}")

        return self._llm

    async def classify(
        self,
        content: str,
        capture_debug: bool = False,
    ) -> tuple[RawClassification, dict[str, str] | None]:
        """Classify document content.

        Args:
            content: Extracted document text content.
            capture_debug: Whether to capture debug info (prompt, response).

        Returns:
            Tuple of (classification result, debug info dict or None).

        Raises:
            LLMParseError: If LLM output cannot be parsed.
            TaxonomyValidationError: If strict mode validation fails.
        """
        # Render prompt with taxonomy menu
        taxonomy_menu = self.taxonomy.to_prompt_menu()
        prompt = self.template.render(
            taxonomy_menu=taxonomy_menu,
            document_content=content,
        )

        debug_info: dict[str, str] | None = None
        if capture_debug:
            debug_info = {"prompt": prompt}

        # Call LLM
        llm = self._get_llm()
        message = HumanMessage(content=prompt)
        response = await llm.ainvoke([message])

        raw_response = response.content
        if capture_debug:
            debug_info["response"] = str(raw_response)

        # Parse JSON response
        classification = self._parse_response(str(raw_response))

        # Normalize with taxonomy
        normalized = self._normalize_classification(classification)

        return normalized, debug_info

    def _parse_response(self, response: str) -> dict:
        """Parse LLM response as JSON.

        Args:
            response: Raw LLM response text.

        Returns:
            Parsed JSON dictionary.

        Raises:
            LLMParseError: If JSON parsing fails.
        """
        # Try to extract JSON from response
        response = response.strip()

        # Try direct parse first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object in response
        json_match = re.search(r"\{[^{}]*\}", response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Try code block extraction
        code_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", response)
        if code_match:
            try:
                return json.loads(code_match.group(1))
            except json.JSONDecodeError:
                pass

        raise LLMParseError(f"Could not parse JSON from response: {response[:200]}...")

    def _normalize_classification(self, raw: dict) -> RawClassification:
        """Normalize classification through taxonomy.

        Args:
            raw: Raw classification dict from LLM.

        Returns:
            Normalized RawClassification.

        Raises:
            TaxonomyValidationError: If strict mode and unknown value found.
        """
        # Validate against Pydantic model first
        try:
            classification = RawClassification.model_validate(raw)
        except ValidationError as e:
            raise LLMParseError(f"Invalid classification structure: {e}")

        # Normalize domain
        normalized_domain = self.taxonomy.canonical_domain(classification.domain)
        if normalized_domain is None:
            if self.taxonomy_mode == TaxonomyMode.STRICT:
                raise TaxonomyValidationError(
                    f"Unknown domain '{classification.domain}' not in taxonomy"
                )
            normalized_domain = "other"

        # Normalize category
        normalized_category = self.taxonomy.canonical_category(
            normalized_domain, classification.category
        )
        if normalized_category is None:
            if self.taxonomy_mode == TaxonomyMode.STRICT:
                raise TaxonomyValidationError(
                    f"Unknown category '{classification.category}' for domain '{normalized_domain}'"
                )
            normalized_category = "other"

        # Normalize doctype
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
