"""Configuration management for Drover.

Precedence (highest to lowest):
1. CLI options
2. Config file (drover.yaml or ~/.config/drover/config.yaml)
3. Environment variables (DROVER_*)
4. Defaults
"""

import os
from enum import StrEnum
from pathlib import Path
from typing import Self

import yaml
from pydantic import BaseModel, Field

from drover.sampling import SampleStrategy


class AIProvider(StrEnum):
    """Supported AI providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"


class TaxonomyMode(StrEnum):
    """Taxonomy validation modes."""

    STRICT = "strict"  # Reject unknown values
    FALLBACK = "fallback"  # Map unknown to "other"


class LogLevel(StrEnum):
    """Log level options."""

    QUIET = "quiet"  # JSON output only
    VERBOSE = "verbose"  # Progress messages to stderr
    DEBUG = "debug"  # Detailed debug output


class ErrorMode(StrEnum):
    """Error handling modes."""

    FAIL = "fail"  # Stop on first error
    CONTINUE = "continue"  # Log error, continue batch
    SKIP = "skip"  # Silently skip failures


class AIConfig(BaseModel):
    """AI provider configuration."""

    provider: AIProvider = Field(default=AIProvider.OLLAMA)
    model: str = Field(default="llama3.2:latest")


class DroverConfig(BaseModel):
    """Complete Drover configuration."""

    ai: AIConfig = Field(default_factory=AIConfig)
    taxonomy: str = Field(default="household")
    taxonomy_mode: TaxonomyMode = Field(default=TaxonomyMode.FALLBACK)
    naming_style: str = Field(default="nara")
    sample_strategy: SampleStrategy = Field(default=SampleStrategy.ADAPTIVE)
    max_pages: int = Field(default=10)
    log_level: LogLevel = Field(default=LogLevel.QUIET)
    on_error: ErrorMode = Field(default=ErrorMode.FAIL)
    concurrency: int = Field(default=1)
    metrics: bool = Field(default=False)
    capture_debug: bool = Field(default=False)
    debug_dir: Path | None = Field(
        default=None, description="Directory for debug prompt/response files"
    )

    @classmethod
    def default_config_paths(cls) -> list[Path]:
        """Return default config file locations to search."""
        return [
            Path("drover.yaml"),
            Path("drover.yml"),
            Path.home() / ".config" / "drover" / "config.yaml",
            Path.home() / ".config" / "drover" / "config.yml",
        ]

    @classmethod
    def from_yaml(cls, path: Path) -> Self:
        """Load configuration from a YAML file."""
        with path.open() as f:
            data = yaml.safe_load(f) or {}
        return cls.model_validate(data)

    @classmethod
    def from_env(cls) -> dict:
        """Extract configuration from environment variables."""
        env_map = {
            "DROVER_AI_PROVIDER": ("ai", "provider"),
            "DROVER_AI_MODEL": ("ai", "model"),
            "DROVER_TAXONOMY": ("taxonomy",),
            "DROVER_TAXONOMY_MODE": ("taxonomy_mode",),
            "DROVER_NAMING_STYLE": ("naming_style",),
            "DROVER_SAMPLE_STRATEGY": ("sample_strategy",),
            "DROVER_MAX_PAGES": ("max_pages",),
            "DROVER_LOG_LEVEL": ("log_level",),
            "DROVER_ON_ERROR": ("on_error",),
            "DROVER_CONCURRENCY": ("concurrency",),
            "DROVER_DEBUG_DIR": ("debug_dir",),
        }

        result: dict = {}
        for env_var, path in env_map.items():
            if value := os.environ.get(env_var):
                if len(path) == 2:
                    if path[0] not in result:
                        result[path[0]] = {}
                    result[path[0]][path[1]] = value
                else:
                    if path[0] in ("max_pages", "concurrency"):
                        result[path[0]] = int(value)
                    else:
                        result[path[0]] = value
        return result

    @classmethod
    def load(cls, config_path: Path | None = None) -> Self:
        """Load configuration with full precedence chain.

        Args:
            config_path: Explicit config file path, or None to search defaults.

        Returns:
            Merged configuration from file + environment + defaults.
        """
        file_data: dict = {}

        if config_path and config_path.exists():
            with config_path.open() as f:
                file_data = yaml.safe_load(f) or {}
        else:
            for default_path in cls.default_config_paths():
                if default_path.exists():
                    with default_path.open() as f:
                        file_data = yaml.safe_load(f) or {}
                    break

        env_data = cls.from_env()
        merged = cls._deep_merge(file_data, env_data)

        return cls.model_validate(merged)

    @staticmethod
    def _deep_merge(base: dict, override: dict) -> dict:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = DroverConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def with_overrides(self, **kwargs) -> Self:
        """Return new config with CLI overrides applied.

        Accepts flattened kwargs like ai_provider, ai_model which get
        nested appropriately.
        """
        data = self.model_dump()

        if "ai_provider" in kwargs and kwargs["ai_provider"] is not None:
            data["ai"]["provider"] = kwargs.pop("ai_provider")
        if "ai_model" in kwargs and kwargs["ai_model"] is not None:
            data["ai"]["model"] = kwargs.pop("ai_model")

        for key, value in kwargs.items():
            if value is not None and key in data:
                data[key] = value

        return self.__class__.model_validate(data)
