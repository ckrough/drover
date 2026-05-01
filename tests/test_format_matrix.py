"""Format-coverage matrix: every _SUPPORTED_EXTENSIONS entry through both loaders.

Per spike P0-6: any extension that PASSes under the legacy `unstructured`
loader must not REGRESS under `DoclingLoader` without being explicitly
documented as a known regression. The KNOWN_REGRESSIONS set below
encodes the regressions the spike is currently surfacing for ADR-005;
these xfail rather than fail so CI stays green while the regression
remains visible. Adding a new extension to KNOWN_REGRESSIONS without
a matching entry in `eval/format_matrix.md` (or the ADR) is a no-go
trigger.

See `scripts/format_matrix.py` for the markdown report consumed by
ADR-005 and `eval/format_matrix.md`.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

pytest.importorskip(
    "docling", reason="docling extra not installed; skipping format matrix tests"
)

from drover.loader import (
    _SUPPORTED_EXTENSIONS,
    DoclingLoader,
    DocumentLoader,
    DocumentLoadError,
)
from tests.fixtures.format_matrix.builders import (
    EXT_BUILDERS,
    UNSUPPORTED_BY_BUILDER,
    build_all,
)

if TYPE_CHECKING:
    from pathlib import Path


# Extensions where the docling extra in this environment fails while
# unstructured succeeds. Captured here (not silenced) so prof-nzl /
# ADR-005 can decide whether to keep, fall back, or accept the gap.
KNOWN_REGRESSIONS: frozenset[str] = frozenset({".eml", ".epub", ".rtf"})


@pytest.fixture(autouse=True)
def _bypass_model_preflight() -> pytest.FixtureFunction:
    """Suppress the Docling model cache pre-flight for format-matrix tests.

    This test suite measures format support, not model availability. The
    pre-flight check is bypassed so conversion failures reflect actual
    format incompatibilities, not a missing model cache.
    """
    with patch("drover.loader._check_docling_models_available"):
        yield  # type: ignore[misc]


@pytest.fixture(scope="session")
def format_matrix_fixtures(tmp_path_factory: pytest.TempPathFactory) -> dict[str, Path]:
    """Build one fixture per supported extension once per session."""
    target = tmp_path_factory.mktemp("format_matrix")
    return build_all(target)


def _collect_extensions() -> list[str]:
    """Return the supported extension list in deterministic order."""
    return sorted(_SUPPORTED_EXTENSIONS)


async def _try_load(loader: DocumentLoader | DoclingLoader, path: Path) -> bool:
    """Return True iff the loader produced non-empty content."""
    try:
        loaded = await loader.load(path)
    except DocumentLoadError:
        return False
    return bool(loaded.content.strip())


@pytest.mark.parametrize("ext", _collect_extensions())
def test_format_matrix_no_regress(
    ext: str, format_matrix_fixtures: dict[str, Path]
) -> None:
    """For each extension, fail hard if Docling regresses against unstructured."""
    if ext in UNSUPPORTED_BY_BUILDER:
        pytest.skip(
            f"{ext} requires a Microsoft Office toolchain (libreoffice / "
            f"antiword) to build a synthetic fixture; not in this environment."
        )

    if ext not in EXT_BUILDERS:
        pytest.fail(f"No fixture builder registered for extension: {ext}")

    path = format_matrix_fixtures[ext]

    unstructured_ok = asyncio.run(_try_load(DocumentLoader(), path))
    docling_ok = asyncio.run(_try_load(DoclingLoader(), path))

    if unstructured_ok and not docling_ok:
        if ext in KNOWN_REGRESSIONS:
            pytest.xfail(f"{ext}: known regression under docling — input for ADR-005")
        pytest.fail(
            f"REGRESS: {ext} extracted under unstructured but not docling. "
            f"Add to KNOWN_REGRESSIONS only after ADR-005 documents it; "
            f"otherwise this blocks the spike's go decision."
        )

    if not unstructured_ok and not docling_ok:
        pytest.xfail(f"{ext}: neither loader extracts (no regression)")
