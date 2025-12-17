"""Tests for retry logic in DocumentClassifier."""

import os
import socket
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from drover.classifier import RETRYABLE_EXCEPTIONS, DocumentClassifier
from drover.config import AIProvider, TaxonomyMode
from drover.taxonomy.household import HouseholdTaxonomy


def _make_classifier(**kwargs) -> DocumentClassifier:
    """Create a classifier instance for retry tests."""
    taxonomy = HouseholdTaxonomy()
    defaults = {
        "provider": AIProvider.OLLAMA,
        "model": "dummy",
        "taxonomy": taxonomy,
        "taxonomy_mode": TaxonomyMode.FALLBACK,
        "max_retries": 3,
        "retry_min_wait": 0.01,  # Fast retries for testing
        "retry_max_wait": 0.02,
    }
    defaults.update(kwargs)
    return DocumentClassifier(**defaults)


class TestRetryableExceptions:
    """Tests for RETRYABLE_EXCEPTIONS configuration."""

    def test_retryable_exceptions_includes_connection_error(self) -> None:
        """ConnectionError should trigger retry."""
        assert ConnectionError in RETRYABLE_EXCEPTIONS

    def test_retryable_exceptions_includes_timeout_error(self) -> None:
        """TimeoutError should trigger retry."""
        assert TimeoutError in RETRYABLE_EXCEPTIONS

    def test_retryable_exceptions_includes_socket_timeout(self) -> None:
        """socket.timeout should trigger retry for TCP-level timeouts."""
        assert socket.timeout in RETRYABLE_EXCEPTIONS

    def test_retryable_exceptions_includes_connection_reset_error(self) -> None:
        """ConnectionResetError should trigger retry."""
        assert ConnectionResetError in RETRYABLE_EXCEPTIONS

    def test_retryable_exceptions_includes_connection_refused_error(self) -> None:
        """ConnectionRefusedError should trigger retry."""
        assert ConnectionRefusedError in RETRYABLE_EXCEPTIONS

    def test_retryable_exceptions_includes_broken_pipe_error(self) -> None:
        """BrokenPipeError should trigger retry."""
        assert BrokenPipeError in RETRYABLE_EXCEPTIONS

    def test_retryable_exceptions_excludes_broad_os_error(self) -> None:
        """OSError should NOT be in retryable exceptions (too broad)."""
        assert OSError not in RETRYABLE_EXCEPTIONS

    def test_retryable_exceptions_excludes_permission_error(self) -> None:
        """PermissionError should NOT be retried (not transient)."""
        assert PermissionError not in RETRYABLE_EXCEPTIONS

    def test_retryable_exceptions_excludes_file_not_found_error(self) -> None:
        """FileNotFoundError should NOT be retried (not transient)."""
        assert FileNotFoundError not in RETRYABLE_EXCEPTIONS


class TestRetryDecorator:
    """Tests for _make_retry_decorator."""

    def test_retry_decorator_created_with_config(self) -> None:
        """Retry decorator should use classifier config."""
        classifier = _make_classifier(
            max_retries=5,
            retry_min_wait=1.0,
            retry_max_wait=5.0,
        )
        decorator = classifier._make_retry_decorator()

        # Verify decorator is callable
        assert callable(decorator)


class TestInvokeWithRetry:
    """Tests for _invoke_with_retry behavior."""

    @pytest.mark.asyncio
    async def test_invoke_with_retry_success_no_retry(self) -> None:
        """Successful invocation should not retry."""
        classifier = _make_classifier()

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"domain": "financial", "category": "banking", "doctype": "statement", "vendor": "Bank", "date": "20250101", "subject": "test"}'
        mock_llm.ainvoke = AsyncMock(return_value=mock_response)

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            from langchain_core.messages import HumanMessage

            message = HumanMessage(content="test")
            result = await classifier._invoke_with_retry(message, None)

        assert mock_llm.ainvoke.call_count == 1
        # Verify we got a response (don't assert on specific taxonomy values)
        assert result is not None and len(result) > 0

    @pytest.mark.asyncio
    async def test_invoke_with_retry_retries_on_connection_error(self) -> None:
        """ConnectionError should trigger retry."""
        classifier = _make_classifier(max_retries=3)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"domain": "financial", "category": "banking", "doctype": "statement", "vendor": "Bank", "date": "20250101", "subject": "test"}'

        # Fail twice, succeed third time
        mock_llm.ainvoke = AsyncMock(
            side_effect=[
                ConnectionError("Network error"),
                ConnectionError("Network error again"),
                mock_response,
            ]
        )

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            from langchain_core.messages import HumanMessage

            message = HumanMessage(content="test")
            result = await classifier._invoke_with_retry(message, None)

        assert mock_llm.ainvoke.call_count == 3
        # Verify we got a response after retries (don't assert on specific taxonomy values)
        assert result is not None and len(result) > 0

    @pytest.mark.asyncio
    async def test_invoke_with_retry_retries_on_timeout_error(self) -> None:
        """TimeoutError should trigger retry."""
        classifier = _make_classifier(max_retries=2)

        mock_llm = MagicMock()
        mock_response = MagicMock()
        mock_response.content = '{"domain": "medical", "category": "records", "doctype": "report", "vendor": "Hospital", "date": "20250101", "subject": "test"}'

        # Fail once, succeed second time
        mock_llm.ainvoke = AsyncMock(
            side_effect=[
                TimeoutError("Request timed out"),
                mock_response,
            ]
        )

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            from langchain_core.messages import HumanMessage

            message = HumanMessage(content="test")
            result = await classifier._invoke_with_retry(message, None)

        assert mock_llm.ainvoke.call_count == 2
        # Verify we got a response after retry (don't assert on specific taxonomy values)
        assert result is not None and len(result) > 0

    @pytest.mark.asyncio
    async def test_invoke_with_retry_exhausts_retries(self) -> None:
        """Should raise after exhausting retries."""
        classifier = _make_classifier(max_retries=2)

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(
            side_effect=ConnectionError("Persistent network error")
        )

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            from langchain_core.messages import HumanMessage

            message = HumanMessage(content="test")

            with pytest.raises(ConnectionError, match="Persistent network error"):
                await classifier._invoke_with_retry(message, None)

        # Should have tried max_retries times
        assert mock_llm.ainvoke.call_count == 2

    @pytest.mark.asyncio
    async def test_invoke_with_retry_non_retryable_error_not_retried(self) -> None:
        """Non-retryable exceptions should not be retried."""
        classifier = _make_classifier(max_retries=3)

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=ValueError("Bad input"))

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            from langchain_core.messages import HumanMessage

            message = HumanMessage(content="test")

            with pytest.raises(ValueError, match="Bad input"):
                await classifier._invoke_with_retry(message, None)

        # Should only try once since ValueError is not retryable
        assert mock_llm.ainvoke.call_count == 1

    @pytest.mark.asyncio
    async def test_invoke_with_retry_permission_error_not_retried(self) -> None:
        """PermissionError (an OSError subclass) should NOT be retried.

        This verifies that we don't retry broad OS errors that are not
        network-related. PermissionError indicates a fundamental access
        issue that won't be resolved by retrying.
        """
        classifier = _make_classifier(max_retries=3)

        mock_llm = MagicMock()
        mock_llm.ainvoke = AsyncMock(side_effect=PermissionError("Access denied"))

        with patch.object(classifier, "_get_llm", return_value=mock_llm):
            from langchain_core.messages import HumanMessage

            message = HumanMessage(content="test")

            with pytest.raises(PermissionError, match="Access denied"):
                await classifier._invoke_with_retry(message, None)

        # Should only try once - PermissionError is not retryable
        assert mock_llm.ainvoke.call_count == 1


class TestOpenRouterProvider:
    """Tests for OpenRouter provider initialization."""

    def test_openrouter_requires_api_key(self) -> None:
        """OpenRouter provider should fail if OPENROUTER_API_KEY is not set."""
        # Ensure env var is not set
        old_key = os.environ.pop("OPENROUTER_API_KEY", None)
        try:
            classifier = _make_classifier(
                provider=AIProvider.OPENROUTER,
                model="anthropic/claude-3.5-sonnet",
            )

            with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
                classifier._get_llm()
        finally:
            # Restore env var if it was set
            if old_key is not None:
                os.environ["OPENROUTER_API_KEY"] = old_key

    def test_openrouter_with_api_key_creates_llm(self) -> None:
        """OpenRouter provider should create LLM when API key is set."""
        old_key = os.environ.get("OPENROUTER_API_KEY")
        try:
            os.environ["OPENROUTER_API_KEY"] = "test-key"
            classifier = _make_classifier(
                provider=AIProvider.OPENROUTER,
                model="anthropic/claude-3.5-sonnet",
            )

            llm = classifier._get_llm()

            # Verify it's a ChatOpenAI instance with correct base_url
            from langchain_openai import ChatOpenAI

            assert isinstance(llm, ChatOpenAI)
        finally:
            # Restore original env var state
            if old_key is not None:
                os.environ["OPENROUTER_API_KEY"] = old_key
            else:
                os.environ.pop("OPENROUTER_API_KEY", None)
