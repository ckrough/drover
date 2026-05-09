"""Classification service layer.

Provides a reusable orchestration layer that coordinates configuration,
loading, LLM classification, and path building. The CLI becomes a thin
adapter over this service.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable, Iterator, Sequence
from pathlib import Path

from drover.classifier import (
    ClassificationError,
    DocumentClassifier,
    LLMParseError,
    TaxonomyValidationError,
    TemplateError,
)
from drover.config import (
    DroverConfig,
    ErrorMode,
)
from drover.loader import (
    DoclingLoader,
    DocumentLoadError,
)
from drover.logging import get_logger
from drover.models import ClassificationErrorResult, ClassificationResult, ErrorCode
from drover.naming import get_naming_policy
from drover.path_builder import PathBuilder, PathConstraintError
from drover.taxonomy import get_taxonomy

logger = get_logger(__name__)

Result = ClassificationResult | ClassificationErrorResult
ResultCallback = Callable[[Result], None]


def make_filename_matcher(files: Sequence[Path]) -> Callable[[str], Path | None]:
    """Return a stateful function mapping filename to its next unmatched Path.

    Classification results carry only the basename of the source file
    (``ClassificationResult.original``). Callers reconciling those
    results with their original Path objects need to handle duplicate
    basenames in encounter order. This helper centralizes that logic:
    each call returns the next unconsumed Path for the given filename,
    or ``None`` once every path with that name has been matched.
    """
    index: dict[str, list[Path]] = {}
    for f in files:
        index.setdefault(f.name, []).append(f)
    counters: dict[str, int] = {}

    def match(filename: str) -> Path | None:
        """Return the next unconsumed Path for ``filename`` or None when exhausted."""
        paths = index.get(filename, [])
        idx = counters.get(filename, 0)
        if idx < len(paths):
            counters[filename] = idx + 1
            return paths[idx]
        return None

    return match


def walk_directory(
    root: Path,
    supported_extensions: Iterable[str],
    follow_symlinks: bool = False,
) -> Iterator[tuple[Path, bool]]:
    """Yield files under root paired with whether their extension is supported.

    Hidden files and directories (whose name starts with a dot) are
    skipped. Symlinks are skipped unless ``follow_symlinks`` is True.

    The implementation eagerly materializes the full tree via
    ``sorted(root.rglob('*'))`` to provide deterministic ordering. For
    typical inbox-sized directories this is fine; if you need to walk
    very large trees and care about peak memory, sort outside.

    Args:
        root: Directory to walk.
        supported_extensions: Lowercase suffixes (including the leading
            dot) that count as processable.
        follow_symlinks: When False, symlinked files are skipped. Note
            that ``Path.rglob`` does not descend into symlinked
            directories regardless of this flag — this controls only
            whether individual symlinked files are included.

    Yields:
        Pairs of ``(file_path, is_supported)`` in sorted order.
    """
    extensions = {ext.lower() for ext in supported_extensions}
    for path in sorted(root.rglob("*")):
        if any(part.startswith(".") for part in path.relative_to(root).parts):
            continue
        if path.is_symlink() and not follow_symlinks:
            continue
        if not path.is_file():
            continue
        yield path, path.suffix.lower() in extensions


class ClassificationService:
    """High-level classification pipeline used by the CLI and callers.

    This class owns the core components (loader, classifier, path
    builder) and centralizes error handling and concurrency behavior.
    """

    def __init__(self, config: DroverConfig) -> None:
        self.config = config

        self._taxonomy = get_taxonomy(config.taxonomy)
        self._naming_policy = get_naming_policy(config.naming_style)

        debug_dir = Path(config.debug_dir).expanduser() if config.debug_dir else None
        self._loader = DoclingLoader(
            strategy=config.sample_strategy,
            max_pages=config.max_pages,
            debug_dir=debug_dir,
            debug_structure=config.debug_structure,
        )
        self._classifier = self._create_classifier()
        self._path_builder = PathBuilder(
            naming_policy=self._naming_policy,
            taxonomy=self._taxonomy,
        )

    def _create_classifier(self) -> DocumentClassifier:
        """Create the LLM-based document classifier."""
        cfg = self.config

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
                metrics = debug_info["metrics"]
                metrics["loader_latency_ms"] = loaded.loader_latency_ms
                metrics["loader_backend"] = loaded.loader_backend
                result.metrics = metrics

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
