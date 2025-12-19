"""Tests for NLI document classifier.

These tests verify the NLI classification mechanism without requiring
the actual transformer models (which are mocked).
"""

from unittest.mock import MagicMock, patch

import pytest

from drover.config import TaxonomyMode
from drover.extractors import ExtractionResult, RegexExtractor
from drover.models import RawClassification
from drover.nli_classifier import (
    CATEGORY_TEMPLATES,
    DOCTYPE_TEMPLATES,
    DOMAIN_TEMPLATES,
    NLIClassificationError,
    NLIDocumentClassifier,
    NLIImportError,
    TaxonomyValidationError,
    _label_to_readable,
    generate_category_hypotheses,
    generate_doctype_hypotheses,
    generate_domain_hypotheses,
)
from drover.taxonomy import HouseholdTaxonomy


class TestLabelToReadable:
    """Tests for label formatting helper."""

    def test_underscore_to_space(self) -> None:
        """Underscores are converted to spaces."""
        assert _label_to_readable("financial_aid") == "financial aid"
        assert _label_to_readable("lab_result") == "lab result"

    def test_no_underscores(self) -> None:
        """Labels without underscores are unchanged."""
        assert _label_to_readable("financial") == "financial"
        assert _label_to_readable("tax") == "tax"


class TestHypothesisGeneration:
    """Tests for hypothesis generation functions."""

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        """Create taxonomy instance."""
        return HouseholdTaxonomy()

    def test_domain_hypotheses_cover_all_domains(self, taxonomy: HouseholdTaxonomy) -> None:
        """Domain hypotheses are generated for all domains."""
        hypotheses = generate_domain_hypotheses(taxonomy)
        assert set(hypotheses.keys()) == taxonomy.CANONICAL_DOMAINS

    def test_domain_hypotheses_use_templates(self, taxonomy: HouseholdTaxonomy) -> None:
        """Each domain has hypotheses from all templates."""
        hypotheses = generate_domain_hypotheses(taxonomy)
        for domain, hyp_list in hypotheses.items():
            assert len(hyp_list) == len(DOMAIN_TEMPLATES)
            # Check readable label is in hypotheses
            readable = domain.replace("_", " ")
            assert any(readable in h for h in hyp_list)

    def test_category_hypotheses_domain_specific(self, taxonomy: HouseholdTaxonomy) -> None:
        """Category hypotheses are specific to the given domain."""
        # Get categories for financial domain
        financial_hyps = generate_category_hypotheses(taxonomy, "financial")
        financial_cats = set(taxonomy.categories_for_domain("financial"))
        assert set(financial_hyps.keys()) == financial_cats

        # Get categories for medical domain - should be different
        medical_hyps = generate_category_hypotheses(taxonomy, "medical")
        medical_cats = set(taxonomy.categories_for_domain("medical"))
        assert set(medical_hyps.keys()) == medical_cats

        # Verify no overlap (categories are domain-specific)
        assert financial_cats != medical_cats

    def test_category_hypotheses_include_domain_context(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """Category hypotheses include domain context."""
        hypotheses = generate_category_hypotheses(taxonomy, "financial")
        for hyp_list in hypotheses.values():
            # At least one hypothesis should mention "financial"
            assert any("financial" in h for h in hyp_list)

    def test_doctype_hypotheses_cover_all_doctypes(self, taxonomy: HouseholdTaxonomy) -> None:
        """Doctype hypotheses are generated for all doctypes."""
        hypotheses = generate_doctype_hypotheses(taxonomy)
        assert set(hypotheses.keys()) == taxonomy.CANONICAL_DOCTYPES

    def test_doctype_hypotheses_use_templates(self, taxonomy: HouseholdTaxonomy) -> None:
        """Each doctype has hypotheses from all templates."""
        hypotheses = generate_doctype_hypotheses(taxonomy)
        for doctype, hyp_list in hypotheses.items():
            assert len(hyp_list) == len(DOCTYPE_TEMPLATES)


class TestRegexExtractor:
    """Tests for regex-based metadata extraction."""

    @pytest.fixture
    def extractor(self) -> RegexExtractor:
        """Create extractor instance."""
        return RegexExtractor()

    # --- Date extraction tests ---

    def test_extract_date_iso_format(self, extractor: RegexExtractor) -> None:
        """ISO date format (YYYY-MM-DD) is extracted."""
        content = "Document dated 2024-01-15 for review."
        result = extractor.extract(content)
        assert result.date == "20240115"

    def test_extract_date_us_format(self, extractor: RegexExtractor) -> None:
        """US date format (MM/DD/YYYY) is extracted."""
        content = "Statement for 01/15/2024"
        result = extractor.extract(content)
        assert result.date == "20240115"

    def test_extract_date_written_format(self, extractor: RegexExtractor) -> None:
        """Written date format (Month DD, YYYY) is extracted."""
        content = "Effective January 15, 2024"
        result = extractor.extract(content)
        assert result.date == "20240115"

    def test_extract_date_written_abbreviated(self, extractor: RegexExtractor) -> None:
        """Abbreviated month format (Jan 15, 2024) is extracted."""
        content = "Due: Jan 15, 2024"
        result = extractor.extract(content)
        assert result.date == "20240115"

    def test_extract_date_unknown(self, extractor: RegexExtractor) -> None:
        """Missing date returns 'unknown'."""
        content = "This document has no date."
        result = extractor.extract(content)
        assert result.date == "unknown"

    # --- Vendor extraction tests ---

    def test_extract_vendor_from_line(self, extractor: RegexExtractor) -> None:
        """Vendor extracted from 'From:' line."""
        content = "From: Acme Corporation\n\nDear Customer,"
        result = extractor.extract(content)
        assert "Acme" in result.vendor

    def test_extract_vendor_with_suffix(self, extractor: RegexExtractor) -> None:
        """Vendor with company suffix is extracted."""
        content = "Bank of America Inc.\n123 Main Street"
        result = extractor.extract(content)
        assert "Bank of America" in result.vendor

    def test_extract_vendor_unknown(self, extractor: RegexExtractor) -> None:
        """Missing vendor returns 'unknown'."""
        content = "just some random text without any identifiable patterns here."
        result = extractor.extract(content)
        assert result.vendor == "unknown"

    # --- Subject extraction tests ---

    def test_extract_subject_first_meaningful_line(self, extractor: RegexExtractor) -> None:
        """Subject is extracted from first meaningful line."""
        content = "\n\n\nYour Monthly Statement Summary\n\nAccount details below."
        result = extractor.extract(content)
        assert "Monthly Statement" in result.subject

    def test_extract_subject_default(self, extractor: RegexExtractor) -> None:
        """Short lines return 'document' default."""
        content = "A\nB\nC\nD\n"
        result = extractor.extract(content)
        assert result.subject == "document"


class TestNLIDocumentClassifier:
    """Tests for NLI document classifier."""

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        """Create taxonomy instance."""
        return HouseholdTaxonomy()

    @pytest.fixture
    def mock_extractor(self) -> MagicMock:
        """Create mock extractor."""
        extractor = MagicMock()
        extractor.extract.return_value = ExtractionResult(
            vendor="Test Vendor",
            date="20240115",
            subject="Test Subject",
        )
        return extractor

    def test_normalize_classification_valid(self, taxonomy: HouseholdTaxonomy) -> None:
        """Valid classification is normalized correctly."""
        classifier = NLIDocumentClassifier(taxonomy=taxonomy)
        raw = RawClassification(
            domain="financial",
            category="banking",
            doctype="statement",
            vendor="Test",
            date="20240101",
            subject="Test",
        )
        normalized = classifier._normalize_classification(raw)
        assert normalized.domain == "financial"
        assert normalized.category == "banking"
        assert normalized.doctype == "statement"

    def test_normalize_classification_fallback_mode(self, taxonomy: HouseholdTaxonomy) -> None:
        """Unknown values map to 'other' in fallback mode."""
        classifier = NLIDocumentClassifier(
            taxonomy=taxonomy,
            taxonomy_mode=TaxonomyMode.FALLBACK,
        )
        raw = RawClassification(
            domain="unknown_domain",
            category="unknown_category",
            doctype="unknown_doctype",
            vendor="Test",
            date="20240101",
            subject="Test",
        )
        normalized = classifier._normalize_classification(raw)
        assert normalized.domain == "other"
        assert normalized.category == "other"
        assert normalized.doctype == "other"

    def test_normalize_classification_strict_mode_raises(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """Unknown values raise in strict mode."""
        classifier = NLIDocumentClassifier(
            taxonomy=taxonomy,
            taxonomy_mode=TaxonomyMode.STRICT,
        )
        raw = RawClassification(
            domain="unknown_domain",
            category="banking",
            doctype="statement",
            vendor="Test",
            date="20240101",
            subject="Test",
        )
        with pytest.raises(TaxonomyValidationError, match="Unknown domain"):
            classifier._normalize_classification(raw)

    def test_import_error_when_deps_missing(self, taxonomy: HouseholdTaxonomy) -> None:
        """NLIImportError raised when transformers not installed."""
        classifier = NLIDocumentClassifier(taxonomy=taxonomy)

        with patch.dict("sys.modules", {"torch": None, "transformers": None}):
            # Force reimport check
            classifier._torch = None
            with pytest.raises(NLIImportError):
                classifier._ensure_dependencies()


class TestNLIClassifierIntegration:
    """Integration tests for NLI classifier (with mocked model).

    Note: Full integration tests require transformers/torch to be installed.
    These tests focus on the classifier logic with mocked dependencies.
    """

    @pytest.fixture
    def taxonomy(self) -> HouseholdTaxonomy:
        """Create taxonomy instance."""
        return HouseholdTaxonomy()

    def test_classify_sync_with_mocked_scoring(
        self, taxonomy: HouseholdTaxonomy
    ) -> None:
        """_classify_sync works with mocked entailment scoring."""
        classifier = NLIDocumentClassifier(taxonomy=taxonomy)

        # Mock the _compute_entailment_score to return predictable values
        call_count = {"n": 0}

        def mock_score(premise: str, hypothesis: str) -> float:
            call_count["n"] += 1
            # Return high score for "financial" domain hypothesis
            if "financial" in hypothesis.lower():
                return 0.9
            # Return high score for "banking" category hypothesis
            if "banking" in hypothesis.lower():
                return 0.85
            # Return high score for "statement" doctype hypothesis
            if "statement" in hypothesis.lower():
                return 0.8
            return 0.1

        # Patch the scoring method
        with patch.object(
            classifier, "_compute_entailment_score", side_effect=mock_score
        ):
            # Patch truncation to return content as-is
            with patch.object(
                classifier, "_truncate_content", return_value="Bank statement content"
            ):
                result, debug = classifier._classify_sync(
                    "Bank of America statement showing balance",
                    capture_debug=True,
                )

                assert isinstance(result, RawClassification)
                assert result.domain == "financial"
                assert result.category == "banking"
                assert result.doctype == "statement"
                assert debug is not None
                assert "domain_scores" in debug
                assert call_count["n"] > 0  # Verify scoring was called


class TestExtractionResult:
    """Tests for ExtractionResult dataclass."""

    def test_extraction_result_immutable(self) -> None:
        """ExtractionResult is frozen (immutable)."""
        result = ExtractionResult(
            vendor="Test",
            date="20240101",
            subject="Test Subject",
        )
        with pytest.raises(AttributeError):
            result.vendor = "Modified"  # type: ignore

    def test_extraction_result_unknown_factory(self) -> None:
        """ExtractionResult.unknown() creates default result."""
        result = ExtractionResult.unknown()
        assert result.vendor == "unknown"
        assert result.date == "unknown"
        assert result.subject == "document"

    def test_extraction_result_with_confidence(self) -> None:
        """ExtractionResult can include confidence scores."""
        result = ExtractionResult(
            vendor="Test",
            date="20240101",
            subject="Test Subject",
            confidence={"vendor": 0.9, "date": 0.8, "subject": 0.7},
        )
        assert result.confidence is not None
        assert result.confidence["vendor"] == 0.9
