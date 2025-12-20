"""Tests for JSON parsing in DocumentClassifier._parse_response."""

from drover.classifier import DocumentClassifier, LLMParseError
from drover.config import AIProvider, TaxonomyMode
from drover.taxonomy.household import HouseholdTaxonomy


def _make_classifier() -> DocumentClassifier:
    """Create a classifier instance suitable for parsing tests.

    The LLM is not invoked in these tests; only _parse_response is used.
    """
    taxonomy = HouseholdTaxonomy()
    return DocumentClassifier(
        provider=AIProvider.OLLAMA,
        model="dummy",
        taxonomy=taxonomy,
        taxonomy_mode=TaxonomyMode.FALLBACK,
    )


def test_parse_response_direct_json() -> None:
    classifier = _make_classifier()
    payload = (
        '{"domain": "financial", "category": "banking", "doctype": "statement", '
        '"vendor": "Bank", "date": "20250101", "subject": "checking"}'
    )

    result = classifier._parse_response(payload)

    assert result["domain"] == "financial"
    assert result["doctype"] == "statement"


def test_parse_response_json_in_code_block() -> None:
    classifier = _make_classifier()
    # Long line intentional - simulates realistic LLM output in code block
    payload = """Here is the answer:
```json
{"domain": "financial", "category": "banking", "doctype": "statement", "vendor": "Bank", "date": "20250101", "subject": "checking"}
```
"""  # noqa: E501

    result = classifier._parse_response(payload)

    assert result["category"] == "banking"


def test_parse_response_balanced_object_inside_text() -> None:
    classifier = _make_classifier()
    payload = (
        'Some explanation before {\n  "domain": "financial",\n  "category": "banking",'
        '\n  "doctype": "statement",\n  "vendor": "Bank",\n  "date": "20250101",'
        '\n  "subject": "checking"\n} and some trailing text.'
    )

    result = classifier._parse_response(payload)

    assert result["vendor"] == "Bank"


def test_parse_response_raises_on_invalid_json() -> None:
    classifier = _make_classifier()
    payload = "not valid json here"

    try:
        classifier._parse_response(payload)
    except LLMParseError as exc:  # noqa: PT011
        assert "Could not parse JSON" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected LLMParseError for invalid JSON response")


def test_parse_response_double_brace_wrapper() -> None:
    """LLM sometimes mirrors `{{ ... }}` examples from the prompt template."""
    classifier = _make_classifier()
    payload = """{{
  "domain": "financial",
  "category": "banking",
  "doctype": "statement",
  "vendor": "Bank",
  "date": "20250101",
  "subject": "checking"
}}"""

    result = classifier._parse_response(payload)

    assert result["domain"] == "financial"
    assert result["category"] == "banking"


def test_parse_response_classification_analysis_tags() -> None:
    """LLM produces chain-of-thought inside <classification_analysis> tags."""
    classifier = _make_classifier()
    payload = """<classification_analysis>
## Step 1: Extract Key Information

- **Organizations:** "First National Bank"
- **Dates:** "Statement Date: January 15, 2025"
- **Document structure:** Bank statement format

## Step 2: Evaluate Dates by Priority

The statement date January 15, 2025 is Priority 2.
Converting: January = 01, 15, 2025 → 20250115

## Step 3-7: Additional analysis...

Final verification complete.
</classification_analysis>
{
  "domain": "financial",
  "category": "banking",
  "doctype": "statement",
  "vendor": "First National Bank",
  "date": "20250115",
  "subject": "account summary"
}"""

    result = classifier._parse_response(payload)

    assert result["domain"] == "financial"
    assert result["category"] == "banking"
    assert result["doctype"] == "statement"
    assert result["vendor"] == "First National Bank"
    assert result["date"] == "20250115"
    assert result["subject"] == "account summary"
