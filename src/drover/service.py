"""Classification service layer.

Provides a reusable orchestration layer that coordinates configuration,
loading, LLM classification, and path building. The CLI becomes a thin
adapter over this service.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import TYPE_CHECKING

from drover.classifier import (
    ClassificationError,
    DocumentClassifier,
    LLMParseError,
    TaxonomyValidationError,
    TemplateError,
)
from drover.config import AIProvider, DroverConfig, ErrorMode, ExtractorType
from drover.loader import DocumentLoader, DocumentLoadError
from drover.logging import get_logger
from drover.models import ClassificationErrorResult, ClassificationResult, ErrorCode
from drover.naming import get_naming_policy
from drover.nli_classifier import (
    NLIClassificationError,
    NLIImportError,
)
from drover.nli_classifier import (
    TaxonomyValidationError as NLITaxonomyValidationError,
)
from drover.path_builder import PathBuilder, PathConstraintError
from drover.taxonomy import get_taxonomy

if TYPE_CHECKING:
    from drover.nli_classifier import NLIDocumentClassifier

logger = get_logger(__name__)

Result = ClassificationResult | ClassificationErrorResult
ResultCallback = Callable[[Result], None]


class ClassificationService:
    """High-level classification pipeline used by the CLI and callers.

    This class owns the core components (loader, classifier, path
    builder) and centralizes error handling and concurrency behavior.
    """

    def __init__(self, config: DroverConfig) -> None:
        self.config = config

        self._taxonomy = get_taxonomy(config.taxonomy)
        self._naming_policy = get_naming_policy(config.naming_style)

        self._loader = DocumentLoader(
            strategy=config.sample_strategy,
            max_pages=config.max_pages,
        )
        self._classifier = self._create_classifier()
        self._path_builder = PathBuilder(naming_policy=self._naming_policy)

    def _create_classifier(self) -> DocumentClassifier | NLIDocumentClassifier:
        """Create classifier based on configured provider.

        Returns:
            DocumentClassifier for LLM providers, NLIDocumentClassifier for NLI_LOCAL.
        """
        cfg = self.config

        if cfg.ai.provider == AIProvider.NLI_LOCAL:
            return self._create_nli_classifier()

        return DocumentClassifier(
            provider=cfg.ai.provider,
            model=cfg.ai.model,
            taxonomy=self._taxonomy,
            taxonomy_mode=cfg.taxonomy_mode,
            template_path=cfg.prompt,
            temperature=cfg.ai.temperature,
            max_tokens=cfg.ai.max_tokens,
            timeout=cfg.ai.timeout,
            max_retries=cfg.ai.max_retries,
            retry_min_wait=cfg.ai.retry_min_wait,
            retry_max_wait=cfg.ai.retry_max_wait,
        )

    def _create_nli_classifier(self) -> NLIDocumentClassifier:
        """Create NLI classifier with configured extractor."""
        from drover.extractors import HybridExtractor, RegexExtractor
        from drover.nli_classifier import NLIDocumentClassifier

        cfg = self.config
        nli_cfg = cfg.nli

        # Create extractor based on config
        if nli_cfg.extractor == ExtractorType.HYBRID and nli_cfg.fallback_model:
            from drover.extractors import create_ollama_extractor

            extractor = create_ollama_extractor(model=nli_cfg.fallback_model)
        elif nli_cfg.extractor == ExtractorType.HYBRID:
            extractor = HybridExtractor()  # No LLM fallback configured
        else:
            extractor = RegexExtractor()

        return NLIDocumentClassifier(
            taxonomy=self._taxonomy,
            taxonomy_mode=cfg.taxonomy_mode,
            extractor=extractor,
            model_name=nli_cfg.model_name,
            device=nli_cfg.device,
            max_tokens=nli_cfg.max_tokens,
        )

    async def classify_files(
        self,
        files: Sequence[Path],
        on_result: ResultCallback | None = None,
    ) -> int:
        """Classify multiple files with concurrency and error modes.

        Args:
            files: File paths to classify.
            on_result: Optional callback invoked for each emitted result.

        Returns:
            Exit code (0=success, 1=partial failure, 2=complete failure).
        """
        if not files:
            return 0

        semaphore = asyncio.Semaphore(self.config.concurrency)
        errors = 0

        async def process(file_path: Path) -> Result:
            async with semaphore:
                return await self.classify_file(file_path)

        tasks = [process(path) for path in files]

        for coro in asyncio.as_completed(tasks):
            result = await coro

            is_error = isinstance(result, ClassificationErrorResult) or result.error
            if is_error:
                errors += 1
                if self.config.on_error == ErrorMode.FAIL:
                    if on_result is not None:
                        on_result(result)
                    return 2
                if self.config.on_error == ErrorMode.SKIP:
                    continue

            if on_result is not None:
                on_result(result)

        if errors == len(files):
            return 2
        if errors > 0:
            return 1
        return 0

    async def classify_file(self, file_path: Path) -> Result:
        """Classify a single file and map errors to result models."""
        cfg = self.config

        logger.debug("file_processing_started", file=str(file_path))

        try:
            loaded = await self._loader.load(file_path)

            classification, debug_info = await self._classifier.classify(
                content=loaded.content,
                capture_debug=cfg.capture_debug,
                collect_metrics=cfg.metrics,
            )

            if cfg.capture_debug and debug_info:
                self._save_debug_files(file_path, debug_info)

            result = self._path_builder.build(classification, file_path)

            if cfg.metrics and debug_info and "metrics" in debug_info:
                result.metrics = debug_info["metrics"]

            logger.debug(
                "file_processing_complete",
                file=str(file_path),
                suggested_path=result.suggested_path,
            )

            return result

        except DocumentLoadError as e:
            logger.warning(
                "file_load_failed",
                file=str(file_path),
                error=str(e),
            )
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.DOCUMENT_LOAD_FAILED,
                e,
            )
        except LLMParseError as e:
            logger.warning(
                "llm_parse_failed",
                file=str(file_path),
                error=str(e),
            )
            self._save_debug_from_exception(file_path, e)
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.LLM_PARSE_ERROR,
                e,
            )
        except TaxonomyValidationError as e:
            logger.warning(
                "taxonomy_validation_failed",
                file=str(file_path),
                error=str(e),
            )
            self._save_debug_from_exception(file_path, e)
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.TAXONOMY_VALIDATION_FAILED,
                e,
            )
        except PathConstraintError as e:
            logger.warning(
                "path_constraint_failed",
                file=str(file_path),
                error=str(e),
            )
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.FILENAME_POLICY_VIOLATION,
                e,
            )
        except TemplateError as e:
            logger.error(
                "template_error",
                file=str(file_path),
                error=str(e),
            )
            self._save_debug_from_exception(file_path, e)
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.TEMPLATE_ERROR,
                e,
            )
        except ClassificationError as e:
            logger.error(
                "llm_api_error",
                file=str(file_path),
                error=str(e),
            )
            self._save_debug_from_exception(file_path, e)
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.LLM_API_ERROR,
                e,
            )
        except NLIImportError as e:
            logger.error(
                "nli_import_error",
                file=str(file_path),
                error=str(e),
            )
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.CONFIG_ERROR,
                e,
            )
        except NLITaxonomyValidationError as e:
            logger.warning(
                "nli_taxonomy_validation_failed",
                file=str(file_path),
                error=str(e),
            )
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.TAXONOMY_VALIDATION_FAILED,
                e,
            )
        except NLIClassificationError as e:
            logger.error(
                "nli_classification_error",
                file=str(file_path),
                error=str(e),
            )
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.LLM_API_ERROR,  # Reuse for NLI errors
                e,
            )
        except Exception as e:  # defensive fallback for unexpected errors
            logger.exception(
                "unexpected_error",
                file=str(file_path),
                error=str(e),
            )
            return ClassificationErrorResult.from_exception(
                file_path.name,
                ErrorCode.UNEXPECTED_ERROR,
                e,
            )

    def _save_debug_from_exception(
        self, file_path: Path, exc: ClassificationError
    ) -> None:
        """Save debug info from an exception if capture_debug is enabled.

        Extracts debug_info from ClassificationError exceptions (which may
        contain prompt and response data) and saves to disk for debugging
        failed classifications.
        """
        if not self.config.capture_debug:
            return

        debug_info = getattr(exc, "debug_info", None)
        if debug_info is not None:
            self._save_debug_files(file_path, debug_info)

    def _save_debug_files(self, file_path: Path, debug_info: dict[str, object]) -> None:
        """Save debug information (prompt/response) to disk.

        If `config.debug_dir` is set, files are written there and name
        collisions are avoided by appending a numeric suffix. Otherwise,
        files are written next to the original document.
        """
        cfg = self.config

        if cfg.debug_dir is not None:
            debug_root = Path(cfg.debug_dir).expanduser()
            debug_root.mkdir(parents=True, exist_ok=True)
            stem = file_path.stem
            base = debug_root / stem
        else:
            base = file_path.with_suffix("")

        prompt = debug_info.get("prompt")
        if isinstance(prompt, str):
            prompt_file = self._unique_debug_path(base.with_suffix(".prompt.txt"))
            prompt_file.write_text(prompt)

        response = debug_info.get("response")
        if isinstance(response, str):
            response_file = self._unique_debug_path(base.with_suffix(".response.txt"))
            response_file.write_text(response)

    @staticmethod
    def _unique_debug_path(base: Path) -> Path:
        """Return a unique path by appending a numeric suffix if needed."""
        if not base.exists():
            return base

        idx = 1
        while True:
            candidate = base.with_name(f"{base.stem}_{idx}{base.suffix}")
            if not candidate.exists():
                return candidate
            idx += 1
