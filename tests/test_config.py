"""Tests for configuration management."""

import os
from pathlib import Path
from unittest.mock import patch

from drover.config import (
    AIConfig,
    AIProvider,
    DroverConfig,
    ErrorMode,
    LogLevel,
    SampleStrategy,
    TaxonomyMode,
)


class TestDroverConfig:
    """Tests for DroverConfig."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = DroverConfig()

        assert config.ai.provider == AIProvider.OLLAMA
        assert config.ai.model == "llama3.2:latest"
        assert config.taxonomy == "household"
        assert config.taxonomy_mode == TaxonomyMode.FALLBACK
        assert config.naming_style == "nara"
        assert config.sample_strategy == SampleStrategy.ADAPTIVE
        assert config.max_pages == 10
        assert config.log_level == LogLevel.QUIET
        assert config.on_error == ErrorMode.FAIL
        assert config.concurrency == 1
        assert config.metrics is False
        assert config.capture_debug is False

    def test_from_dict(self) -> None:
        """Test creating config from dictionary."""
        data = {
            "ai": {"provider": "openai", "model": "gpt-4"},
            "taxonomy": "custom",
            "max_pages": 5,
        }
        config = DroverConfig.model_validate(data)

        assert config.ai.provider == AIProvider.OPENAI
        assert config.ai.model == "gpt-4"
        assert config.taxonomy == "custom"
        assert config.max_pages == 5

    def test_with_overrides_ai_provider(self) -> None:
        """Test CLI overrides for AI provider."""
        config = DroverConfig()
        new_config = config.with_overrides(ai_provider="openai")

        assert new_config.ai.provider == AIProvider.OPENAI
        # Original unchanged
        assert config.ai.provider == AIProvider.OLLAMA

    def test_with_overrides_ai_model(self) -> None:
        """Test CLI overrides for AI model."""
        config = DroverConfig()
        new_config = config.with_overrides(ai_model="gpt-4-turbo")

        assert new_config.ai.model == "gpt-4-turbo"

    def test_with_overrides_none_values_ignored(self) -> None:
        """Test None values are not applied as overrides."""
        config = DroverConfig()
        new_config = config.with_overrides(
            ai_provider=None,
            taxonomy=None,
            max_pages=None,
        )

        # Should keep original values
        assert new_config.ai.provider == AIProvider.OLLAMA
        assert new_config.taxonomy == "household"
        assert new_config.max_pages == 10

    def test_with_overrides_multiple(self) -> None:
        """Test multiple overrides at once."""
        config = DroverConfig()
        new_config = config.with_overrides(
            ai_provider="anthropic",
            ai_model="claude-3-sonnet",
            taxonomy="custom",
            max_pages=20,
            log_level="verbose",
        )

        assert new_config.ai.provider == AIProvider.ANTHROPIC
        assert new_config.ai.model == "claude-3-sonnet"
        assert new_config.taxonomy == "custom"
        assert new_config.max_pages == 20
        assert new_config.log_level == LogLevel.VERBOSE

    def test_from_env_ai_settings(self) -> None:
        """Test loading AI settings from environment."""
        with patch.dict(
            os.environ,
            {
                "DROVER_AI_PROVIDER": "openai",
                "DROVER_AI_MODEL": "gpt-4",
            },
        ):
            env_data = DroverConfig.from_env()

        assert env_data["ai"]["provider"] == "openai"
        assert env_data["ai"]["model"] == "gpt-4"

    def test_from_env_numeric_values(self) -> None:
        """Test numeric environment variable conversion."""
        with patch.dict(
            os.environ,
            {
                "DROVER_MAX_PAGES": "15",
                "DROVER_CONCURRENCY": "4",
            },
        ):
            env_data = DroverConfig.from_env()

        assert env_data["max_pages"] == 15
        assert env_data["concurrency"] == 4

    def test_from_env_ai_retry_settings(self) -> None:
        """Test loading AI retry settings from environment."""
        with patch.dict(
            os.environ,
            {
                "DROVER_AI_TEMPERATURE": "0.7",
                "DROVER_AI_MAX_TOKENS": "2000",
                "DROVER_AI_TIMEOUT": "120",
                "DROVER_AI_MAX_RETRIES": "5",
                "DROVER_AI_RETRY_MIN_WAIT": "1.0",
                "DROVER_AI_RETRY_MAX_WAIT": "30.0",
            },
        ):
            env_data = DroverConfig.from_env()

        assert env_data["ai"]["temperature"] == 0.7
        assert env_data["ai"]["max_tokens"] == 2000
        assert env_data["ai"]["timeout"] == 120
        assert env_data["ai"]["max_retries"] == 5
        assert env_data["ai"]["retry_min_wait"] == 1.0
        assert env_data["ai"]["retry_max_wait"] == 30.0

    def test_deep_merge(self) -> None:
        """Test deep merge of dictionaries."""
        base = {"ai": {"provider": "ollama", "model": "llama3"}, "taxonomy": "household"}
        override = {"ai": {"model": "mistral"}, "max_pages": 5}

        result = DroverConfig._deep_merge(base, override)

        assert result["ai"]["provider"] == "ollama"  # Not overridden
        assert result["ai"]["model"] == "mistral"  # Overridden
        assert result["taxonomy"] == "household"  # Not overridden
        assert result["max_pages"] == 5  # Added

    def test_default_config_paths(self) -> None:
        """Test default config path list."""
        paths = DroverConfig.default_config_paths()

        assert isinstance(paths, list)
        assert len(paths) > 0
        assert any("drover.yaml" in str(p) for p in paths)

    def test_prompt_default_none(self) -> None:
        """Test prompt defaults to None."""
        config = DroverConfig()
        assert config.prompt is None

    def test_prompt_from_dict(self) -> None:
        """Test setting prompt from dictionary."""
        data = {"prompt": "/path/to/custom.md"}
        config = DroverConfig.model_validate(data)
        assert config.prompt == Path("/path/to/custom.md")

    def test_prompt_with_overrides(self) -> None:
        """Test prompt CLI override."""
        config = DroverConfig()
        new_config = config.with_overrides(prompt=Path("/custom/prompt.md"))
        assert new_config.prompt == Path("/custom/prompt.md")

    def test_prompt_from_env(self) -> None:
        """Test loading prompt from environment."""
        with patch.dict(os.environ, {"DROVER_PROMPT": "/env/prompt.md"}):
            env_data = DroverConfig.from_env()
        assert env_data["prompt"] == "/env/prompt.md"


class TestAIConfig:
    """Tests for AIConfig."""

    def test_default_values(self) -> None:
        """Test default AI config values."""
        config = AIConfig()
        assert config.provider == AIProvider.OLLAMA
        assert config.model == "llama3.2:latest"
        assert config.temperature == 0.0
        assert config.max_tokens == 1000
        assert config.timeout == 60
        assert config.max_retries == 3
        assert config.retry_min_wait == 2.0
        assert config.retry_max_wait == 10.0

    def test_custom_values(self) -> None:
        """Test custom AI config values."""
        config = AIConfig(provider=AIProvider.OPENAI, model="gpt-4-turbo")
        assert config.provider == AIProvider.OPENAI
        assert config.model == "gpt-4-turbo"

    def test_temperature_bounds(self) -> None:
        """Test temperature validation bounds."""
        import pytest

        config = AIConfig(temperature=0.5)
        assert config.temperature == 0.5

        config = AIConfig(temperature=2.0)
        assert config.temperature == 2.0

        with pytest.raises(ValueError):
            AIConfig(temperature=-0.1)

        with pytest.raises(ValueError):
            AIConfig(temperature=2.1)

    def test_retry_wait_validation_valid(self) -> None:
        """Test valid retry wait range."""
        config = AIConfig(retry_min_wait=1.0, retry_max_wait=5.0)
        assert config.retry_min_wait == 1.0
        assert config.retry_max_wait == 5.0

        # Equal values are valid
        config = AIConfig(retry_min_wait=3.0, retry_max_wait=3.0)
        assert config.retry_min_wait == 3.0
        assert config.retry_max_wait == 3.0

    def test_retry_wait_validation_invalid(self) -> None:
        """Test invalid retry wait range raises error."""
        import pytest

        with pytest.raises(ValueError, match="retry_min_wait.*must be <= retry_max_wait"):
            AIConfig(retry_min_wait=10.0, retry_max_wait=5.0)

    def test_timeout_validation(self) -> None:
        """Test timeout must be positive."""
        import pytest

        config = AIConfig(timeout=30)
        assert config.timeout == 30

        with pytest.raises(ValueError):
            AIConfig(timeout=0)

    def test_max_retries_bounds(self) -> None:
        """Test max_retries validation bounds."""
        import pytest

        config = AIConfig(max_retries=1)
        assert config.max_retries == 1

        config = AIConfig(max_retries=10)
        assert config.max_retries == 10

        with pytest.raises(ValueError):
            AIConfig(max_retries=0)

        with pytest.raises(ValueError):
            AIConfig(max_retries=11)
