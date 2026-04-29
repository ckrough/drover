"""Classification evaluation framework.

Enables systematic measurement of classification accuracy against ground truth
data, supporting model comparison, prompt optimization, and regression testing.

Example usage:
    evaluator = ClassificationEvaluator(ground_truth_path="eval/ground_truth.jsonl")
    results = await evaluator.evaluate(classifier, test_files)
    print(f"Domain accuracy: {results.domain_accuracy:.1%}")
"""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from drover.classifier import DocumentClassifier
from drover.loader import DoclingLoader, DocumentLoader
from drover.logging import get_logger
from drover.models import RawClassification

if TYPE_CHECKING:
    from drover.nli_classifier import NLIDocumentClassifier

# Either classifier path is acceptable to the evaluator. Both expose the same
# minimal surface used here: `classify(content) -> (RawClassification, ...)`,
# `.model`, and `.provider`. PEP 695 `type` keeps the NLI import deferred.
type EvaluableClassifier = DocumentClassifier | NLIDocumentClassifier

logger = get_logger(__name__)


class GroundTruthEntry(BaseModel):
    """A single ground truth entry for evaluation."""

    filename: str = Field(description="Document filename (without path)")
    domain: str = Field(description="Expected domain classification")
    category: str = Field(description="Expected category classification")
    doctype: str = Field(description="Expected document type")
    vendor: str | None = Field(default=None, description="Expected vendor (optional)")
    date: str | None = Field(default=None, description="Expected date (optional)")
    subject: str | None = Field(default=None, description="Expected subject (optional)")
    notes: str | None = Field(default=None, description="Notes about this entry")


@dataclass
class ClassificationComparison:
    """Comparison between predicted and actual classification."""

    filename: str
    predicted: RawClassification
    actual: GroundTruthEntry
    domain_correct: bool
    category_correct: bool
    doctype_correct: bool
    vendor_correct: bool | None  # None if vendor not in ground truth
    date_correct: bool | None  # None if date not in ground truth
    loader_latency_ms: float | None = None
    loader_backend: str | None = None


@dataclass
class EvaluationResult:
    """Results of classification evaluation."""

    total: int
    domain_accuracy: float
    category_accuracy: float
    doctype_accuracy: float
    vendor_accuracy: float | None  # None if no vendor data
    date_accuracy: float | None  # None if no date data

    # Detailed results per file
    comparisons: list[ClassificationComparison] = field(default_factory=list)

    # Confusion tracking for analysis
    domain_confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    category_confusion: dict[str, dict[str, int]] = field(default_factory=dict)
    doctype_confusion: dict[str, dict[str, int]] = field(default_factory=dict)

    # Metadata
    model: str = ""
    provider: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "total": self.total,
            "domain_accuracy": self.domain_accuracy,
            "category_accuracy": self.category_accuracy,
            "doctype_accuracy": self.doctype_accuracy,
            "vendor_accuracy": self.vendor_accuracy,
            "date_accuracy": self.date_accuracy,
            "model": self.model,
            "provider": self.provider,
            "comparisons": [
                {
                    "filename": c.filename,
                    "predicted": c.predicted.model_dump(),
                    "actual": c.actual.model_dump(),
                    "domain_correct": c.domain_correct,
                    "category_correct": c.category_correct,
                    "doctype_correct": c.doctype_correct,
                    "vendor_correct": c.vendor_correct,
                    "date_correct": c.date_correct,
                    "loader_latency_ms": c.loader_latency_ms,
                    "loader_backend": c.loader_backend,
                }
                for c in self.comparisons
            ],
            "domain_confusion": self.domain_confusion,
            "category_confusion": self.category_confusion,
            "doctype_confusion": self.doctype_confusion,
        }

    def summary(self) -> str:
        """Generate human-readable summary."""
        lines = [
            f"Evaluation Results ({self.provider}/{self.model})",
            f"{'=' * 50}",
            f"Total documents: {self.total}",
            f"Domain accuracy:   {self.domain_accuracy:6.1%}",
            f"Category accuracy: {self.category_accuracy:6.1%}",
            f"Doctype accuracy:  {self.doctype_accuracy:6.1%}",
        ]
        if self.vendor_accuracy is not None:
            lines.append(f"Vendor accuracy:   {self.vendor_accuracy:6.1%}")
        if self.date_accuracy is not None:
            lines.append(f"Date accuracy:     {self.date_accuracy:6.1%}")

        # Show misclassifications
        mistakes = [c for c in self.comparisons if not c.domain_correct]
        if mistakes:
            lines.append(f"\nDomain misclassifications ({len(mistakes)}):")
            for c in mistakes[:5]:  # Show first 5
                lines.append(
                    f"  {c.filename}: {c.actual.domain} -> {c.predicted.domain}"
                )
            if len(mistakes) > 5:
                lines.append(f"  ... and {len(mistakes) - 5} more")

        return "\n".join(lines)


class ClassificationEvaluator:
    """Evaluates classification accuracy against ground truth.

    Loads ground truth data from a JSONL file where each line contains
    a GroundTruthEntry with expected classification fields.

    Example ground_truth.jsonl::

        {"filename": "bank.pdf", "domain": "financial", "category": "banking", ...}
        {"filename": "bill.pdf", "domain": "financial", "category": "utilities", ...}
    """

    def __init__(
        self,
        ground_truth_path: str | Path,
        documents_dir: str | Path | None = None,
    ) -> None:
        """Initialize evaluator with ground truth data.

        Args:
            ground_truth_path: Path to JSONL file with ground truth entries.
            documents_dir: Directory containing test documents.
                          If None, uses directory containing ground_truth_path.
        """
        self.ground_truth_path = Path(ground_truth_path)
        self.documents_dir = (
            Path(documents_dir)
            if documents_dir
            else self.ground_truth_path.parent / "documents"
        )
        self.ground_truth: dict[str, GroundTruthEntry] = {}
        self._load_ground_truth()

    def _load_ground_truth(self) -> None:
        """Load ground truth entries from JSONL file."""
        if not self.ground_truth_path.exists():
            raise FileNotFoundError(
                f"Ground truth file not found: {self.ground_truth_path}"
            )

        with self.ground_truth_path.open() as f:
            for line_num, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                try:
                    data = json.loads(line)
                    entry = GroundTruthEntry.model_validate(data)
                    self.ground_truth[entry.filename] = entry
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(
                        "ground_truth_parse_error",
                        line=line_num,
                        error=str(e),
                    )

        logger.info(
            "ground_truth_loaded",
            entries=len(self.ground_truth),
            path=str(self.ground_truth_path),
        )

    async def evaluate(
        self,
        classifier: EvaluableClassifier,
        test_files: Sequence[str | Path] | None = None,
        loader: DocumentLoader | DoclingLoader | None = None,
    ) -> EvaluationResult:
        """Run classification on test files and compare to ground truth.

        Args:
            classifier: Configured DocumentClassifier instance.
            test_files: Specific files to test. If None, uses all files
                       that have ground truth entries.
            loader: Document loader for text extraction. If None, creates
                a default `DocumentLoader` (unstructured backend).

        Returns:
            EvaluationResult with accuracy metrics and detailed comparisons.
        """
        if loader is None:
            loader = DocumentLoader()

        # Determine files to evaluate
        if test_files is None:
            # Find all files that have ground truth
            test_files = []
            for filename in self.ground_truth:
                file_path = self.documents_dir / filename
                if file_path.exists():
                    test_files.append(file_path)
                else:
                    logger.warning(
                        "ground_truth_file_missing",
                        filename=filename,
                        expected_path=str(file_path),
                    )

        comparisons: list[ClassificationComparison] = []
        domain_correct = 0
        category_correct = 0
        doctype_correct = 0
        vendor_correct = 0
        vendor_total = 0
        date_correct = 0
        date_total = 0

        # Confusion matrices
        domain_confusion: dict[str, dict[str, int]] = {}
        category_confusion: dict[str, dict[str, int]] = {}
        doctype_confusion: dict[str, dict[str, int]] = {}

        for fp in test_files:
            resolved_path = Path(fp)
            filename = resolved_path.name

            # Get ground truth
            actual = self.ground_truth.get(filename)
            if actual is None:
                logger.warning(
                    "no_ground_truth",
                    filename=filename,
                )
                continue

            # Load and classify document
            try:
                loaded_doc = await loader.load(resolved_path)
                predicted, _ = await classifier.classify(
                    loaded_doc.content, docling_doc=loaded_doc.docling_doc
                )
            except Exception as e:
                logger.error(
                    "classification_error",
                    filename=filename,
                    error=str(e),
                )
                continue

            # Compare results
            d_correct = predicted.domain.lower() == actual.domain.lower()
            c_correct = predicted.category.lower() == actual.category.lower()
            t_correct = predicted.doctype.lower() == actual.doctype.lower()

            # Vendor comparison (optional)
            v_correct = None
            if actual.vendor is not None:
                v_correct = predicted.vendor.lower() == actual.vendor.lower()
                vendor_total += 1
                if v_correct:
                    vendor_correct += 1

            # Date comparison (optional)
            dt_correct = None
            if actual.date is not None:
                dt_correct = predicted.date == actual.date
                date_total += 1
                if dt_correct:
                    date_correct += 1

            comparison = ClassificationComparison(
                filename=filename,
                predicted=predicted,
                actual=actual,
                domain_correct=d_correct,
                category_correct=c_correct,
                doctype_correct=t_correct,
                vendor_correct=v_correct,
                date_correct=dt_correct,
                loader_latency_ms=loaded_doc.loader_latency_ms,
                loader_backend=loaded_doc.loader_backend,
            )
            comparisons.append(comparison)

            # Update counters
            if d_correct:
                domain_correct += 1
            if c_correct:
                category_correct += 1
            if t_correct:
                doctype_correct += 1

            # Update confusion matrices
            self._update_confusion(domain_confusion, actual.domain, predicted.domain)
            self._update_confusion(
                category_confusion, actual.category, predicted.category
            )
            self._update_confusion(doctype_confusion, actual.doctype, predicted.doctype)

            logger.debug(
                "evaluated",
                filename=filename,
                domain_correct=d_correct,
                category_correct=c_correct,
                doctype_correct=t_correct,
            )

        # Calculate accuracies
        total = len(comparisons)
        if total == 0:
            return EvaluationResult(
                total=0,
                domain_accuracy=0.0,
                category_accuracy=0.0,
                doctype_accuracy=0.0,
                vendor_accuracy=None,
                date_accuracy=None,
                model=classifier.model,
                provider=classifier.provider.value,
            )

        return EvaluationResult(
            total=total,
            domain_accuracy=domain_correct / total,
            category_accuracy=category_correct / total,
            doctype_accuracy=doctype_correct / total,
            vendor_accuracy=vendor_correct / vendor_total if vendor_total > 0 else None,
            date_accuracy=date_correct / date_total if date_total > 0 else None,
            comparisons=comparisons,
            domain_confusion=domain_confusion,
            category_confusion=category_confusion,
            doctype_confusion=doctype_confusion,
            model=classifier.model,
            provider=classifier.provider.value,
        )

    @staticmethod
    def _update_confusion(
        confusion: dict[str, dict[str, int]],
        actual: str,
        predicted: str,
    ) -> None:
        """Update confusion matrix."""
        actual = actual.lower()
        predicted = predicted.lower()
        if actual not in confusion:
            confusion[actual] = {}
        if predicted not in confusion[actual]:
            confusion[actual][predicted] = 0
        confusion[actual][predicted] += 1


async def compare_models(
    classifier_a: EvaluableClassifier,
    classifier_b: EvaluableClassifier,
    ground_truth_path: str | Path,
    documents_dir: str | Path | None = None,
) -> tuple[EvaluationResult, EvaluationResult]:
    """Compare two classifiers on the same ground truth data.

    Useful for A/B testing different models or prompt versions.

    Args:
        classifier_a: First classifier to evaluate.
        classifier_b: Second classifier to evaluate.
        ground_truth_path: Path to ground truth JSONL file.
        documents_dir: Directory containing test documents.

    Returns:
        Tuple of (results_a, results_b) for comparison.
    """
    evaluator = ClassificationEvaluator(ground_truth_path, documents_dir)

    results_a = await evaluator.evaluate(classifier_a)
    results_b = await evaluator.evaluate(classifier_b)

    return results_a, results_b
