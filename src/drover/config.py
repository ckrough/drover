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
from typing import Any, Self

import yaml
from pydantic import BaseModel, Field, model_validator

from drover.sampling import SampleStrategy


class AIProvider(StrEnum):
    """Supported AI providers."""

    OLLAMA = "ollama"
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OPENROUTER = "openrouter"


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


class LoaderType(StrEnum):
    """Document loader backend."""

    UNSTRUCTURED = "unstructured"  # Fallback: unstructured.partition.auto
    DOCLING = "docling"  # Default: structure-aware loader (Docling)


class AIConfig(BaseModel):
    """AI provider configuration."""

    provider: AIProvider = Field(default=AIProvider.OLLAMA)
    model: str = Field(default="gemma4:latest")
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=1000, ge=1)
    timeout: int = Field(default=60, ge=1, description="Request timeout in seconds")
    max_retries: int = Field(default=3, ge=1, le=10)
    retry_min_wait: float = Field(default=2.0, ge=0.1)
    retry_max_wait: float = Field(default=10.0, ge=1.0)

    @model_validator(mode="after")
    def validate_retry_wait_range(self) -> Self:
        """Validate that retry_min_wait <= retry_max_wait."""
        if self.retry_min_wait > self.retry_max_wait:
            raise ValueError(
                f"retry_min_wait ({self.retry_min_wait}) must be <= "
                f"retry_max_wait ({self.retry_max_wait})"
            )
        return self


class DroverConfig(BaseModel):
    """Complete Drover configuration."""

    ai: AIConfig = Field(default_factory=AIConfig)
    taxonomy: str = Field(default="household")
    taxonomy_mode: TaxonomyMode = Field(default=TaxonomyMode.FALLBACK)
    naming_style: str = Field(default="nara")
    sample_strategy: SampleStrategy = Field(default=SampleStrategy.ADAPTIVE)
    max_pages: int = Field(default=10)
    loader: LoaderType = Field(
        default=LoaderType.DOCLING,
        description="Document loader backend (docling | unstructured)",
    )
    log_level: LogLevel = Field(default=LogLevel.QUIET)
    on_error: ErrorMode = Field(default=ErrorMode.FAIL)
    concurrency: int = Field(default=1)
    metrics: bool = Field(default=False)
    capture_debug: bool = Field(default=False)
    debug_structure: bool = Field(
        default=False,
        description="Dump DoclingDocument JSON to debug_dir for inspection",
    )
    debug_dir: Path | None = Field(
        default=None, description="Directory for debug prompt/response files"
    )
    prompt: Path | None = Field(
        default=None, description="Custom prompt template file path"
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
    def from_env(cls) -> dict[str, Any]:
        """Extract configuration from environment variables."""
        env_map = {
            "DROVER_AI_PROVIDER": ("ai", "provider"),
            "DROVER_AI_MODEL": ("ai", "model"),
            "DROVER_AI_TEMPERATURE": ("ai", "temperature"),
            "DROVER_AI_MAX_TOKENS": ("ai", "max_tokens"),
            "DROVER_AI_TIMEOUT": ("ai", "timeout"),
            "DROVER_AI_MAX_RETRIES": ("ai", "max_retries"),
            "DROVER_AI_RETRY_MIN_WAIT": ("ai", "retry_min_wait"),
            "DROVER_AI_RETRY_MAX_WAIT": ("ai", "retry_max_wait"),
            "DROVER_TAXONOMY": ("taxonomy",),
            "DROVER_TAXONOMY_MODE": ("taxonomy_mode",),
            "DROVER_NAMING_STYLE": ("naming_style",),
            "DROVER_SAMPLE_STRATEGY": ("sample_strategy",),
            "DROVER_MAX_PAGES": ("max_pages",),
            "DROVER_LOADER": ("loader",),
            "DROVER_LOG_LEVEL": ("log_level",),
            "DROVER_ON_ERROR": ("on_error",),
            "DROVER_CONCURRENCY": ("concurrency",),
            "DROVER_DEBUG_DIR": ("debug_dir",),
            "DROVER_PROMPT": ("prompt",),
        }

        # Fields that need numeric conversion
        int_fields = {
            "max_pages",
            "concurrency",
            "max_tokens",
            "timeout",
            "max_retries",
        }
        float_fields = {"temperature", "retry_min_wait", "retry_max_wait"}

        result: dict[str, Any] = {}
        for env_var, path in env_map.items():
            if value := os.environ.get(env_var):
                field_name = path[-1]  # Last element is the field name
                if len(path) == 2:
                    if path[0] not in result:
                        result[path[0]] = {}
                    if field_name in int_fields:
                        result[path[0]][field_name] = int(value)
                    elif field_name in float_fields:
                        result[path[0]][field_name] = float(value)
                    else:
                        result[path[0]][field_name] = value
                else:
                    if field_name in int_fields:
                        result[field_name] = int(value)
                    elif field_name in float_fields:
                        result[field_name] = float(value)
                    else:
                        result[field_name] = value
        return result

    @classmethod
    def load(cls, config_path: Path | None = None) -> Self:
        """Load configuration with full precedence chain.

        Args:
            config_path: Explicit config file path, or None to search defaults.

        Returns:
            Merged configuration from file + environment + defaults.
        """
        file_data: dict[str, Any] = {}

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
    def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
        """Deep merge two dictionaries, with override taking precedence."""
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = DroverConfig._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def with_overrides(self, **kwargs: Any) -> Self:
        """Return new config with CLI overrides applied.

        Accepts flattened kwargs like ai_provider, ai_model which get
        nested appropriately.
        """
        data = self.model_dump()

        if "ai_provider" in kwargs and kwargs["ai_provider"] is not None:
            data["ai"]["provider"] = kwargs.pop("ai_provider")
        if "ai_model" in kwargs and kwargs["ai_model"] is not None:
            data["ai"]["model"] = kwargs.pop("ai_model")
        if "ai_max_tokens" in kwargs and kwargs["ai_max_tokens"] is not None:
            data["ai"]["max_tokens"] = kwargs.pop("ai_max_tokens")

        for key, value in kwargs.items():
            if value is not None and key in data:
                data[key] = value

        return self.__class__.model_validate(data)
