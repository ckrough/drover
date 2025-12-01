"""Pydantic models for document classification."""

from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field


class ErrorCode(StrEnum):
    """Error codes for classification failures."""

    DOCUMENT_LOAD_FAILED = "DOCUMENT_LOAD_FAILED"
    LLM_PARSE_ERROR = "LLM_PARSE_ERROR"
    LLM_API_ERROR = "LLM_API_ERROR"
    TAXONOMY_VALIDATION_FAILED = "TAXONOMY_VALIDATION_FAILED"
    CONFIG_ERROR = "CONFIG_ERROR"


class ClassificationResult(BaseModel):
    """Result of document classification."""

    original: str = Field(description="Original filename")
    suggested_path: str = Field(description="Suggested file path")
    domain: str = Field(description="Top-level domain (e.g., financial, medical)")
    category: str = Field(description="Category within domain (e.g., banking, tax)")
    doctype: str = Field(description="Document type (e.g., statement, receipt)")
    vendor: str = Field(description="Vendor/provider name, normalized")
    date: str = Field(description="Document date in YYYYMMDD format")
    subject: str = Field(description="Brief subject description")
    error: bool = Field(default=False, description="Whether classification failed")
    error_code: ErrorCode | None = Field(default=None, description="Error code if failed")
    error_message: str | None = Field(default=None, description="Error message if failed")


class ClassificationError(BaseModel):
    """Error result when classification fails."""

    original: str = Field(description="Original filename")
    error: bool = Field(default=True)
    error_code: ErrorCode = Field(description="Error code")
    error_message: str = Field(description="Human-readable error message")

    @classmethod
    def from_exception(
        cls, filename: str | Path, code: ErrorCode, exception: Exception
    ) -> "ClassificationError":
        """Create error result from an exception."""
        return cls(
            original=str(filename),
            error_code=code,
            error_message=str(exception),
        )


class RawClassification(BaseModel):
    """Raw classification output from LLM before normalization."""

    domain: str = Field(description="Domain identified by LLM")
    category: str = Field(description="Category identified by LLM")
    doctype: str = Field(description="Document type identified by LLM")
    vendor: str = Field(description="Vendor name as identified")
    date: str = Field(description="Date in YYYYMMDD format")
    subject: str = Field(description="Subject description")


class PathConstraints(BaseModel):
    """Constraints for generated file paths."""

    max_path_length: int = Field(default=255, description="Maximum total path length")
    max_folder_depth: int = Field(default=4, description="Maximum folder nesting depth")
    allowed_chars: str = Field(
        default="a-z0-9_-", description="Regex pattern for allowed characters"
    )
