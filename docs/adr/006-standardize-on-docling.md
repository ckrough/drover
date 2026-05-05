# ADR-006: Standardize on Docling, Remove `unstructured` Fallback

## Status

Accepted (2026-05-05). Supersedes-in-part [ADR-005](005-docling-evaluation.md): the unstructured fallback path is removed.

## Context

ADR-005 made Docling with full-page OCR the default loader and kept `unstructured` as a documented fallback for formats where Docling regressed (`.eml`, `.epub`, `.rtf`) or for users who preferred the lighter dependency tree. The dual-loader configuration carried ongoing cost without ongoing benefit:

- **CLI surface:** `--loader docling|unstructured` and `DROVER_LOADER` had to be plumbed through every command, the `DroverConfig` model, the test helpers, and the documentation.
- **Test infrastructure:** `tests/test_format_matrix.py`, `tests/fixtures/format_matrix/builders.py`, and `scripts/build_format_matrix.py` existed solely to compare the two loaders. The xfail markers carried "input for ADR-005" framing that became stale once ADR-005 was accepted.
- **Dependency weight:** `unstructured[pdf,docx,xlsx,pptx,md,rtf]` pulled in ~50 transitive packages (rapidfuzz, pdfminer.six, python-magic, NLTK data, etc.) that the live code path did not need.
- **Conceptual ambiguity:** an "officially supported" extension list that mixed Docling-supported formats with unstructured-supported formats invited misuse. A user with a `.rtf` file got a hard failure under the default loader and had to know to switch backends.

The cleaner stance: Docling is the loader. Formats Docling does not officially support are simply not supported.

## Decision

Remove the `unstructured` backend and standardize on Docling as the sole loader.

Concretely:

1. Delete `DocumentLoader` (the `unstructured` backend) from `src/drover/loader.py`.
2. Delete `LoaderType` enum from `src/drover/config.py` and the `loader` field from `DroverConfig`.
3. Delete the `--loader` CLI flag from every command and the `DROVER_LOADER` environment variable.
4. Drop `unstructured[pdf,docx,xlsx,pptx,md,rtf]` from `pyproject.toml`; regenerate `uv.lock`.
5. Delete the format-matrix infrastructure (`scripts/build_format_matrix.py`, `tests/test_format_matrix.py`, `tests/fixtures/format_matrix/builders.py`, `eval/format_matrix.md`).
6. Reduce `_SUPPORTED_EXTENSIONS` to exactly what Docling officially supports per [`docs/usage/supported_formats`](https://docling-project.github.io/docling/usage/supported_formats/).

### Format-Support Audit

Source: Docling official documentation (`docs/usage/supported_formats.md` and the project README features list), retrieved 2026-05-05.

**Kept (officially supported by Docling):**

| Category | Extensions |
|---|---|
| PDF | `.pdf` |
| Office (Open XML) | `.docx`, `.xlsx`, `.pptx` |
| Markup | `.txt`, `.md`, `.html`, `.htm` |
| Data | `.csv` |
| Images | `.png`, `.jpg`, `.jpeg`, `.tiff`, `.tif`, `.bmp` |

15 extensions total. The supported set is locked by `tests/test_loader.py::test_supported_extensions_match_docling_audit` so accidental additions surface as test failures and force a deliberate review against the upstream support table.

**Removed (not in Docling's documented support):**

| Extension | Reason |
|---|---|
| `.doc`, `.xls`, `.ppt` | Legacy MS Office binary formats. Docling lists only Office Open XML. |
| `.gif` | Not in Docling's documented image set (PNG, JPEG, TIFF, BMP, WEBP). |
| `.tsv` | Docling lists CSV only; TSV is not officially supported. |
| `.eml`, `.epub`, `.odt`, `.rtf` | Never reliably handled by Docling; previously were the `unstructured` fallback case. |

`.webp` is officially supported by Docling but is not added in this ADR (out of scope: this change only removes formats; additions belong in a separate proposal).

## Consequences

- **Drover users with files in the removed extensions get a clear `Unsupported file type` error from `DoclingLoader.load()`** rather than silent regression or a model-cache failure. Previous behaviour for these formats was either a hard error under the default Docling loader or a fallback to `unstructured` via opt-in flag; the loader-selection decision is removed from the user's hands.
- **`.eml`, `.epub`, `.rtf` regressions are accepted, not papered over.** A future fix is possible but out of scope for this ADR (e.g., per-format pre-processors that emit text Docling can accept, or revisiting Docling support if the upstream catalogue grows). The point of this ADR is to stop maintaining a second loader to paper over the gap.
- **CLI surface shrinks.** No `--loader` option. The Pydantic config model loses `LoaderType` and the `loader` field. `DROVER_LOADER` is no longer read.
- **Dependency tree shrinks.** `uv lock` regeneration removes ~50 packages from `uv.lock`.
- **Tests get faster and more representative.** The format-matrix parametrized tests are gone; the remaining test suite all exercises the live (Docling) loader path or stubs it explicitly.
- **Documentation simplifies.** No two-loader guidance, no NLTK setup step, no fallback section.

## Verification

Captured at the time of acceptance:

- `uv run pytest`: 237 passed, 5 skipped, 0 xfailed (`test_format_matrix.py` xfails are gone with the file).
- `uv run ruff check src/ tests/ scripts/`: clean.
- `uv run ruff format src/ tests/ scripts/ --check`: clean.
- `uv run mypy src/`: clean.
- `uv run bandit -r src/`: 0 results at medium severity / medium confidence.
- `grep -rn "unstructured" src/ tests/ scripts/`: no live code references; only ADR-005 / ADR-006 historical cross-references remain.
