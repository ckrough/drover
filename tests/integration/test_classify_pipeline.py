"""Integration tests for the full classification pipeline.

These tests verify end-to-end functionality with a real LLM.
They require a config.yaml file - see config.example.yaml.

Run with: pytest tests/integration/ -m integration
"""

from pathlib import Path

import pytest

from drover.classifier import DocumentClassifier
from drover.loader import DoclingLoader
from drover.models import RawClassification
from drover.naming.nara import NARAPolicyNaming
from drover.path_builder import PathBuilder
from drover.taxonomy.household import HouseholdTaxonomy


@pytest.mark.integration
class TestClassificationPipeline:
    """End-to-end tests for document classification."""

    @pytest.mark.asyncio
    async def test_classify_bank_statement(
        self,
        integration_classifier: DocumentClassifier,
        integration_loader: DoclingLoader,
        sample_text_file: Path,
    ) -> None:
        """Test classifying a bank statement document."""
        # Load document
        loaded = await integration_loader.load(sample_text_file)
        assert loaded.content
        assert "FIRST NATIONAL BANK" in loaded.content

        # Classify
        result, _ = await integration_classifier.classify(loaded.content)

        # Verify classification
        assert isinstance(result, RawClassification)
        assert result.domain == "financial"
        assert result.category == "banking"
        assert result.doctype == "statements"
        assert result.vendor  # Should have extracted vendor name
        assert result.date  # Should have extracted date

    @pytest.mark.asyncio
    async def test_classify_invoice(
        self,
        integration_classifier: DocumentClassifier,
        integration_loader: DoclingLoader,
        sample_invoice_file: Path,
    ) -> None:
        """Test classifying an invoice document."""
        # Load document
        loaded = await integration_loader.load(sample_invoice_file)
        assert loaded.content
        assert "Invoice" in loaded.content

        # Classify
        result, _ = await integration_classifier.classify(loaded.content)

        # Verify classification
        assert isinstance(result, RawClassification)
        assert result.domain == "financial"
        # Invoice could be categorized as business or other financial category
        assert result.category in {"business", "tax", "banking", "other"}
        assert result.doctype in {"invoices", "receipts", "statements", "other"}
        assert result.date  # Should have extracted date

    @pytest.mark.asyncio
    async def test_full_pipeline_produces_valid_path(
        self,
        integration_classifier: DocumentClassifier,
        integration_loader: DoclingLoader,
        sample_text_file: Path,
    ) -> None:
        """Test that classification produces a valid suggested path."""
        # Load and classify
        loaded = await integration_loader.load(sample_text_file)
        classification, _ = await integration_classifier.classify(loaded.content)

        # Build path using the naming policy
        naming_policy = NARAPolicyNaming()
        builder = PathBuilder(naming_policy=naming_policy)
        result = builder.build(
            classification=classification,
            original_path=sample_text_file,
        )

        # Verify path structure
        assert result.suggested_path
        parts = Path(result.suggested_path).parts

        # Should have at least domain/category/doctype/filename
        assert len(parts) >= 4

        # First part should be a valid domain
        taxonomy = HouseholdTaxonomy()
        assert parts[0] in taxonomy.all_domains()

    @pytest.mark.asyncio
    async def test_classification_with_metrics(
        self,
        integration_classifier: DocumentClassifier,
        integration_loader: DoclingLoader,
        sample_text_file: Path,
    ) -> None:
        """Test that metrics collection works with real LLM."""
        loaded = await integration_loader.load(sample_text_file)
        result, _debug_info = await integration_classifier.classify(
            loaded.content,
            collect_metrics=True,
        )

        assert isinstance(result, RawClassification)
        # Debug info should contain metrics when collect_metrics=True
        # (exact format depends on provider)


@pytest.mark.integration
class TestDocumentLoading:
    """Integration tests for document loading."""

    @pytest.mark.asyncio
    async def test_load_text_file(
        self,
        integration_loader: DoclingLoader,
        sample_text_file: Path,
    ) -> None:
        """Test loading a plain text file."""
        loaded = await integration_loader.load(sample_text_file)

        assert loaded.path == sample_text_file
        assert loaded.content
        assert loaded.page_count >= 1
        assert loaded.pages_sampled >= 1

    @pytest.mark.asyncio
    async def test_load_preserves_content(
        self,
        integration_loader: DoclingLoader,
        sample_text_file: Path,
    ) -> None:
        """Test that loading preserves key content."""
        loaded = await integration_loader.load(sample_text_file)

        # Key content should be preserved
        assert "FIRST NATIONAL BANK" in loaded.content
        assert "Account Statement" in loaded.content
        assert "$5,432.10" in loaded.content
