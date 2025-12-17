"""Pytest configuration for integration tests.

Integration tests require a config.yaml file with LLM settings.
Tests are skipped if config.yaml is not present.
"""

from pathlib import Path

import pytest
import yaml

from drover.classifier import DocumentClassifier
from drover.config import AIProvider, DroverConfig, TaxonomyMode
from drover.loader import DocumentLoader
from drover.taxonomy.household import HouseholdTaxonomy

INTEGRATION_DIR = Path(__file__).parent
CONFIG_PATH = INTEGRATION_DIR / "config.yaml"
FIXTURES_DIR = INTEGRATION_DIR / "fixtures"


def pytest_configure(config: pytest.Config) -> None:
    """Register the integration marker."""
    config.addinivalue_line(
        "markers",
        "integration: marks tests as integration tests (require config.yaml)",
    )


@pytest.fixture(scope="session")
def integration_config() -> DroverConfig:
    """Load integration test configuration.

    Skips all integration tests if config.yaml is not present.
    """
    if not CONFIG_PATH.exists():
        pytest.skip(
            f"Integration tests require {CONFIG_PATH}. "
            f"Copy config.example.yaml to config.yaml and configure your LLM."
        )

    with CONFIG_PATH.open() as f:
        data = yaml.safe_load(f) or {}

    return DroverConfig.model_validate(data)


@pytest.fixture(scope="session")
def integration_classifier(integration_config: DroverConfig) -> DocumentClassifier:
    """Create a classifier configured for integration tests."""
    taxonomy = HouseholdTaxonomy()
    return DocumentClassifier(
        provider=AIProvider(integration_config.ai.provider),
        model=integration_config.ai.model,
        taxonomy=taxonomy,
        taxonomy_mode=TaxonomyMode.FALLBACK,
        temperature=integration_config.ai.temperature,
        max_tokens=integration_config.ai.max_tokens,
        timeout=integration_config.ai.timeout,
    )


@pytest.fixture(scope="session")
def integration_loader() -> DocumentLoader:
    """Create a document loader for integration tests."""
    return DocumentLoader()


@pytest.fixture
def sample_text_file(tmp_path: Path) -> Path:
    """Create a sample text file for testing."""
    content = """
    FIRST NATIONAL BANK
    Account Statement

    Account Holder: John Smith
    Account Number: ****1234
    Statement Period: January 1, 2025 - January 31, 2025

    Beginning Balance: $5,432.10

    Transactions:
    01/05/2025  Direct Deposit - Employer    +$3,500.00
    01/10/2025  Electric Company             -$125.50
    01/15/2025  Grocery Store                -$87.23
    01/20/2025  Gas Station                  -$45.00

    Ending Balance: $8,674.37

    Thank you for banking with First National Bank.
    """
    file_path = tmp_path / "bank_statement.txt"
    file_path.write_text(content)
    return file_path


@pytest.fixture
def sample_invoice_file(tmp_path: Path) -> Path:
    """Create a sample invoice file for testing."""
    content = """
    ACME CORPORATION
    Invoice #INV-2025-0042

    Bill To:
    Jane Doe
    123 Main Street
    Anytown, ST 12345

    Invoice Date: February 15, 2025
    Due Date: March 15, 2025

    Description                     Qty    Price      Total
    --------------------------------------------------------
    Professional Services           10     $150.00    $1,500.00
    Software License (Annual)       1      $499.00    $499.00

    Subtotal:                                         $1,999.00
    Tax (8%):                                         $159.92

    TOTAL DUE:                                        $2,158.92

    Payment Terms: Net 30
    """
    file_path = tmp_path / "invoice.txt"
    file_path.write_text(content)
    return file_path
