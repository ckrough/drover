"""Shared sampling strategy definitions for document loading.

This module defines the SampleStrategy enum used by both configuration
and the document loader so they remain in sync.
"""

from enum import StrEnum


class SampleStrategy(StrEnum):
    """Document sampling strategies for large documents.

    Values are string-based for easy use with configuration, CLI options,
    and environment variables.
    """

    FULL = "full"  # Process entire document
    FIRST_N = "first_n"  # First N pages only
    BOOKENDS = "bookends"  # First + last N pages
    ADAPTIVE = "adaptive"  # Auto-select based on doc size/type
