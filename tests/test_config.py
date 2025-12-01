"""Tests for configuration management."""

import os
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


class TestAIConfig:
    """Tests for AIConfig."""

    def test_default_values(self) -> None:
        """Test default AI config values."""
        config = AIConfig()
        assert config.provider == AIProvider.OLLAMA
        assert config.model == "llama3.2:latest"

    def test_custom_values(self) -> None:
        """Test custom AI config values."""
        config = AIConfig(provider=AIProvider.OPENAI, model="gpt-4-turbo")
        assert config.provider == AIProvider.OPENAI
        assert config.model == "gpt-4-turbo"
