---
title: Docling Evaluation Spike for Drover Document Pipeline
prepared_by: Claude (Opus 4.7) with Chris Krough
updated: 2026-04-29T16:46:55-04:00
purpose: Specify a benchmarked evaluation of Docling as a structure-aware replacement for the unstructured loader, with go/no-go criteria for full integration.
tags: [drover, type/research, status/superseded]
aliases: ["Docling Spike PRD"]
---

# Docling Evaluation Spike for Drover Document Pipeline

> **Status: HISTORICAL.** This is the spike PRD that scoped the Docling evaluation. The spike has been completed and the outcome (no-go) is recorded in [ADR-005](../adr/005-docling-evaluation.md). The spike infrastructure has been removed from Drover. References to `nli_classifier.py`, `DoclingLoader`, `--loader docling`, and the Llama 3.2 baseline below describe the spike scaffolding as it existed during evaluation, not Drover's current behavior. The current loader is still `unstructured`, the current classifier is the local LLM path described in [ADR-004](../adr/004-local-llm-as-primary-local-path.md), and there is no NLI classifier.

## Context

Drover today loads documents through `unstructured.partition.auto` (`src/drover/loader.py:22`) and flattens the result to a single text string on `LoadedDocument.content` (`loader.py:31`). All structural cues (headings, tables, reading order, form fields) are discarded before classification. Three downstream consumers all suffer from the same flat-text bottleneck:

- The LLM classifier (`classifier.py`) receives a sampled-pages blob with only newline-as-page-break separation.
- The NLI classifier (`nli_classifier.py`) chunks that blob with token-window heuristics (`TRUNCATE`, `SLIDING`, `IMPORTANCE`) that cannot respect section boundaries.
- The metadata extractors (`extractors/regex.py`, `extractors/llm.py`) regex over the first 2000 characters and have no way to target a "Vendor:" cell in a table or a "Subject:" line in a letterhead.

Docling (IBM Research, MIT, LF AI & Data Foundation) produces a `DoclingDocument` with hierarchical headings, parsed tables, reading order, code/formulas, OCR fallback, and a built-in `HybridChunker` that respects structure. It also adds first-class support for formats Drover does not currently handle well (audio via WAV/MP3, USPTO/JATS/XBRL XML, LaTeX). Adopting Docling could lift classification accuracy, simplify metadata extraction, and expand the supported-format list without leaving the local-only privacy posture (ADR-002).

### Empirical baseline (from `docs/research/nli-vs-llm-notes.md`, 2026-04-29)

The 80-document eval corpus (16 domains × 5 docs, 51% long) gives concrete starting points for any go/no-go thresholds:

| Path | Domain | Category | Doctype | Vendor | Date |
|------|--------|----------|---------|--------|------|
| LLM (Ollama gemma4:latest) | 87.5% | **40.0%** | 86.2% | 78.8% | 88.8% |
| NLI (best of 6-combo matrix) | 3.8% | 2.5% | 6.2% | 1.2% | 77.5% |

The LLM-vs-NLI gap is 11-84pp on every axis. The author of the research notes already concluded that closing 80pp on doctype with chunking changes "is not a research direction" and halted NLI tuning. The implication for this spike is that **the headline LLM bottleneck is category accuracy at 40%**, not doctype (already at 86%). Long, ambiguous documents fail category classification because the LLM cannot see section boundaries; this is exactly what Docling's hierarchical structure addresses.

For NLI, Docling provides diagnostic lift (heading text as direct entailment evidence; table cells for vendor/date) but cannot bridge the 80pp gap. NLI's role in this spike is therefore as a **regression baseline**, not a competitive classification path.

This document scopes a **benchmarked evaluation spike** with explicit go/no-go thresholds before committing to full integration.

## Problem Statement

Drover discards document structure during loading, forcing the classifier and extractors to recover meaning from flat text. The LLM classifier achieves 87.5% domain and 86.2% doctype on the 80-doc corpus, but only **40.0% category** because long, multi-section documents flatten into a wall of paragraphs that the LLM cannot navigate. Metadata extraction is brittle (regex on first 2000 chars: 1.2% NLI vendor accuracy, 78.8% LLM vendor accuracy). The supported-format list is also bounded by what `unstructured` handles well. We need to know whether Docling can replace `unstructured` as the loader and meaningfully improve the LLM category accuracy, the metadata extraction quality, and the format coverage, before investing in a full integration. NLI is in scope only as a regression baseline.

## Goals

1. **Lift LLM category accuracy from 40% toward parity with domain (87.5%) and doctype (86.2%).** Category is the documented LLM bottleneck and is the primary target of the structural-input hypothesis.
2. **Quantify cross-axis accuracy deltas.** Run the existing 80-document eval corpus (`eval/ground_truth.jsonl`) through both pipelines and measure domain, category, doctype, vendor, and date accuracy deltas for the LLM path. Measure NLI deltas as a regression baseline only.
3. **Verify format parity.** Confirm Docling handles every extension currently in `_SUPPORTED_EXTENSIONS` (`loader.py:46-76`), or document the gap.
4. **Measure runtime cost.** Capture per-document load latency, peak memory, and (where relevant) GPU vs CPU behavior on Apple Silicon and a Linux/CUDA box.
5. **Produce a go/no-go decision** with concrete thresholds (see Success Metrics).
6. **Surface integration risk** in a written spike report covering API stability, model download size, telemetry posture, and dependency footprint vs `unstructured`.

## Non-Goals

1. **No production integration in this phase.** Code lives behind a feature flag (`DROVER_LOADER=docling`) or in a parallel branch; it does not become the default.
2. **No prompt redesign.** The spike measures the lift from structure-aware input alone, not from new prompts. Prompt engineering for markdown headings is a follow-on if the spike passes.
3. **No new taxonomy or naming policies.** The output schema stays `RawClassification` (`models.py`).
4. **No multi-modal LLM exploration.** GraniteDocling 258M and other VLM paths are out of scope; we only consume Docling's structural output.
5. **No benchmark of every Docling chunker.** Pick `HybridChunker` as the candidate; do not evaluate `HierarchicalChunker` separately unless `HybridChunker` underperforms.
6. **No attempt to make NLI competitive with the LLM path.** Per the research notes, the gap is too wide to bridge with chunking changes. NLI accuracy is measured but is not gated by go/no-go thresholds.
7. **No NLI hypothesis-template tuning** (Phase 4 of ADR-003 NLI roadmap). The research notes already halted that work; this spike does not revive it.
8. **No fine-tuning** (Phase 5+ of ADR-003). Out of scope, as it was for the prior research.

## User Stories

Drover has a single primary user (the maintainer) plus future evaluators on the existing eval corpus. Stories are framed accordingly.

- **As the maintainer**, I want a measured comparison of Docling vs the current loader on my real eval set, so that I can decide whether the integration cost is justified.
- **As the maintainer**, I want to know exactly which file types regress under Docling, so that I can plan a hybrid fallback if needed (per the "replace entirely" decision, regressions block the go decision).
- **As a future contributor running `drover evaluate`**, I want the new loader to be a drop-in swap with no changes to the eval CLI surface, so that historical baselines remain comparable.
- **As a downstream NLI user**, I want section-aware chunks instead of token-window chunks, so that classification of long PDFs improves without retraining the NLI model.
- **As a downstream extractor**, I want structured table cells and key-value blocks accessible by region, so that vendor and date extraction can target them directly.

## Requirements

### P0 (Must-Have for Spike Completion)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| P0-1 | Add Docling as an optional extra (`[docling]`) in `pyproject.toml`. | `uv sync --extra docling` installs cleanly on macOS arm64 and Linux x86_64. |
| P0-2 | Implement a parallel `DoclingLoader` that returns a new `LoadedDocument` variant exposing the `DoclingDocument` object alongside markdown text. | `LoadedDocument.docling_doc` is `None` when loader is `unstructured`, populated when loader is `docling`. Existing `content` field continues to hold flat text for backward compatibility. |
| P0-3 | Wire the loader behind `DROVER_LOADER` env var and `--loader` CLI flag (default: `unstructured`). | `drover classify --loader docling foo.pdf` runs end-to-end. |
| P0-4 | Plumb structured input into all three consumers: LLM prompt receives markdown-with-headings; NLI uses `HybridChunker` when `docling_doc` is present; extractors get a `structured_regions` accessor for tables and key-value blocks. | Each consumer has a unit test asserting it uses structure when available and falls back gracefully when not. |
| P0-5 | Run `drover evaluate eval/ground_truth.jsonl` under both loaders for both LLM (Ollama llama3.2 + one cloud baseline) and NLI providers. | Results checked into `eval/baselines.md` with per-domain breakdown. |
| P0-6 | Format coverage matrix: every extension in `_SUPPORTED_EXTENSIONS` tested with at least one fixture. | Matrix in spike report with PASS/FAIL/REGRESS per format. |
| P0-7 | Spike report committed to `docs/adr/005-docling-evaluation.md` with measured deltas, runtime cost, and explicit go/no-go recommendation against the success metrics below. | ADR is reviewed and either accepts, rejects, or defers Docling adoption. |

### P1 (Nice-to-Have)

| ID | Requirement | Acceptance Criteria |
|----|-------------|---------------------|
| P1-1 | Add a `--debug-structure` flag that dumps the `DoclingDocument` JSON to `DROVER_DEBUG_DIR` for inspection. | Output is valid JSON conforming to Docling's schema. |
| P1-2 | Capture per-document Docling vs unstructured timing in `metrics.py` so future runs accumulate data. | New metrics fields: `loader_latency_ms`, `loader_backend`. |
| P1-3 | Test OCR fallback on at least one scanned PDF fixture. | Tesseract or RapidOCR engine successfully extracts text where unstructured returns empty. |

### P2 (Future Considerations)

| ID | Requirement |
|----|-------------|
| P2-1 | Expand `_SUPPORTED_EXTENSIONS` to include Docling-only formats: USPTO XML, JATS, XBRL, LaTeX, audio (WAV/MP3 via WebVTT). |
| P2-2 | Replace regex extractors with table-cell-aware extractors that consume `DoclingDocument.tables` directly. |
| P2-3 | Section-level sampling strategy in `sampling.py` that selects by heading hierarchy instead of page index. |
| P2-4 | Cache `DoclingDocument` to disk via JSON serialization to amortize parsing across re-classifications. |

## How Docling Answers the Three Original Questions

This section maps the original prompt to concrete mechanisms, so the spike measures the right things.

### 1. Identifying document categories and purpose

Docling preserves heading hierarchy and reading order, which means the LLM prompt can include real section structure (`# Invoice`, `## Bill To`, `## Line Items`) instead of a wall of paragraph text. The chain-of-thought prompt (ADR-001) currently asks the LLM to infer category and doctype from scattered cues; with structural markdown, both become more directly derivable. Doctype is already at 86.2% on flat text, so the larger headroom is **category** (40%): a "Property Tax Statement" heading paired with parsed line-item tables disambiguates `tax / property` from `tax / income` in ways that flat text cannot. Tables further disambiguate: an invoice has line-item tables; a contract has signature blocks; a tax form has labeled key-value pairs. The spike measures whether feeding markdown-with-tables to the LLM lifts **category** accuracy first, doctype second.

For the NLI classifier specifically, `HybridChunker` produces chunks aligned to sections, so each NLI hypothesis (e.g., "this section is about taxes") is scored against semantically coherent text instead of a 450-token window that may straddle two unrelated sections. The Phase 2 6-combo bench showed sliding/mean lifts NLI doctype from 3.8% to 6.2% (+2.4pp); structure-aware chunking plus heading-text-as-evidence might push that further, but the absolute floor (~6%) is so far below the LLM (~86%) that even a doubling of NLI accuracy does not change the operational recommendation.

### 2. Expanding supported document types

Drover's current 26 extensions all flow through `unstructured`. Docling natively adds:
- **Audio:** WAV, MP3 transcribed to WebVTT, then classifiable as text.
- **Patents and scientific articles:** USPTO XML and JATS XML parsed into structured documents.
- **Financial filings:** XBRL parsed with tagged values intact.
- **LaTeX:** Direct parsing without intermediate PDF rendering.
- **Better OCR fallback:** Tesseract, RapidOCR, and SuryaOCR engines for scanned PDFs and images that unstructured handles poorly.

The spike validates parity on existing formats first (P0-6) before any P2 expansion.

### 3. Encoding and classification benefits of `DoclingDocument`

A `DoclingDocument` exposes:
- **Hierarchical structure:** `body`, `texts`, `tables`, `pictures`, `groups` with parent-child relationships and reading order.
- **Typed regions:** Each text element has a label (heading, paragraph, list-item, caption, footnote) and bounding box.
- **Parsed tables:** Cell-level access via `TableData`, with row and column headers preserved.
- **Markdown export:** `doc.export_to_markdown()` produces a faithful, structure-preserving serialization for prompts.
- **Native chunker integration:** `HybridChunker` walks the tree and yields chunks that respect both token budgets and section boundaries.

For Drover, this unlocks (a) richer LLM prompts with markdown headings and tables, (b) structure-aligned NLI chunks, and (c) targeted metadata extraction by region type instead of regex over flat text. The spike instruments all three.

## Does Docling Change the NLI vs LLM Calculus?

The original question: combined with Docling, does the zero-shot NLI solution become a better option than the local LLM?

**Short answer: No.** Docling helps NLI more than it helps LLM in *relative* terms, but not enough to flip the operational recommendation.

**Reasoning:**

1. **The current gap is structural, not chunking.** The 6-combo Phase 2 bench moved NLI doctype from 3.8% (truncate/max) to 6.2% (sliding/mean). That is the maximum lift the Drover team observed from substituting one chunking strategy for another while holding the model fixed. Docling's `HybridChunker` is a smarter chunker, but it is still chunking. It cannot turn a 184M-parameter cross-encoder with English natural-language hypotheses into a model that knows "Form 1098-T" implies education/tax/tuition without explicit training signal.

2. **Headings-as-evidence helps NLI on doctype, not on category or domain.** A heading like "Lease Agreement" entailment-scored against "this is a lease" probably hits ~0.95. So Docling could plausibly lift NLI doctype from 6% toward 30-50% on this corpus by adding heading text as a strong per-chunk signal. That is a real gain, but the LLM is at 86%, so the gap stays above 35pp.

3. **Domain and category gains are smaller for NLI.** A heading is rarely "this is a medical document" verbatim; domain inference from structure requires combining multiple cues (line items + addresses + amounts + table headers), which is exactly what an LLM does and an NLI cross-encoder does not.

4. **Vendor and date extraction are extractor-bound, not classifier-bound.** Both NLI and LLM share the regex extractor today. Docling's table-cell access could lift vendor accuracy substantially for *both* paths. The LLM's 78.8% baseline already reflects in-context extraction, so its headroom is smaller (~10-15pp). The NLI's 1.2% baseline reflects pure regex, so structured tables could push it to 30-60%. NLI gains more here in absolute pp, but the LLM still ends up higher in absolute terms.

5. **The LLM also gets better with Docling.** If Docling lifts LLM category from 40% to 55-65% (the headline hypothesis of this spike), the LLM moves *further* ahead of NLI on the dimension where NLI is weakest. Docling does not narrow the gap on category; it widens it.

**Where NLI still earns its place** (per the research notes' own §6 conclusion, unchanged by Docling):
- Latency-critical paths where Ollama startup cost is unacceptable.
- On-device deployments with strict memory limits where a 9.6GB Ollama model is too large.
- Deterministic regression-baseline use: NLI gives identical scores across runs, so it serves as a reliable detector of pipeline regressions.

**Operational outcome:** Docling's primary impact lands on the LLM path. The LLM was already the recommended local path per the research notes; Docling reinforces that recommendation by lifting category accuracy, the LLM's only weak axis. NLI gains diagnostic accuracy and stays a regression baseline.

## Success Metrics

### Leading Indicators (measurable during the spike)

LLM path (Ollama gemma4:latest) is the gating path for go/no-go. NLI path is measured but informational only.

| Metric | Current Baseline (gemma4) | Threshold for "Go" |
|--------|---------------------------|---------------------|
| **Category accuracy (LLM)** | **40.0%** | **+10pp or better → 50%+** (headline win) |
| Doctype accuracy (LLM) | 86.2% | No regression; ideally +3pp |
| Domain accuracy (LLM) | 87.5% | No regression; ideally +2pp |
| Vendor extraction accuracy (LLM) | 78.8% | +5pp or better with table-cell extraction |
| Date extraction accuracy (LLM) | 88.8% | No regression |
| Format parity | 26/26 extensions PASS | 26/26 PASS, zero REGRESS |
| Per-doc load latency (PDF, 10pp) | Captured during spike | <2x current loader |
| Cold-start memory footprint | Captured during spike | <2GB additional resident |

NLI informational metrics (no go/no-go threshold):

| Metric | Current Best (6-combo) | Reported in ADR-005 |
|--------|------------------------|---------------------|
| NLI domain accuracy | 3.8% | Measured with `HybridChunker` |
| NLI category accuracy | 2.5% | Measured with `HybridChunker` |
| NLI doctype accuracy | 6.2% | Measured with `HybridChunker` |
| NLI vendor accuracy (regex on structured regions) | 1.2% | Measured separately |

### Lagging Indicators (post-integration, if go)

- Drover issue tracker shows fewer "garbled extraction" or "missed table" bug reports across the next quarter.
- The eval corpus expands to include audio, XML, and scanned-PDF fixtures (currently impossible or low-quality).
- Multi-LLM matrix becomes feasible: with structural input held constant, comparing gemma4 vs Anthropic Haiku vs Qwen3 measures model capability rather than loader noise.

### No-Go Triggers

Any one of these blocks integration:
- Category accuracy fails to lift by at least 5pp (the entire premise of the spike).
- Doctype accuracy regresses by 2pp or more.
- Domain accuracy regresses by 2pp or more.
- Any current format moves from PASS to FAIL.
- Per-doc latency exceeds 5x current loader.
- Docling pulls a non-MIT transitive dependency or a runtime-network-call requirement that conflicts with ADR-002 privacy posture.

## Open Questions

- **[Engineering]** Does Docling's `HybridChunker` accept arbitrary tokenizers, or is it tied to specific embedding models? This affects compatibility with the DeBERTa-v3 NLI tokenizer.
- **[Engineering]** What is the model download size on first run, and can it be cached in `~/.cache/docling` cleanly? ADR-002 (privacy-first) requires no network calls after install; we must verify no telemetry.
- **[Maintainer]** If Docling passes, do we keep `unstructured` as a fallback for failed Docling parses, or remove it entirely? The scoping decision says "replace entirely," but a runtime fallback is different from a code fallback. **Default assumption: remove entirely on go, no runtime fallback.**
- **[Maintainer]** Should the spike include a cloud LLM baseline (Anthropic + prompt caching) in addition to Ollama, given prompt-caching dynamics shift when input tokens grow with structured markdown? **Default assumption: include one cloud run to capture cache-hit-rate impact.**
- **[Engineering]** Does `DoclingDocument` serialize cleanly to JSON for caching, or does it embed model artifacts that block round-tripping?

## Timeline Considerations

Per `~/.claude/rules/internal-docs.md`, no time estimates are committed. Phasing only:

1. **Phase A: Setup.** Add `[docling]` extra, write `DoclingLoader`, wire CLI flag (P0-1, P0-2, P0-3).
2. **Phase B: Consumer plumbing.** Update LLM prompt path, NLI chunker path, extractor accessors (P0-4).
3. **Phase C: Benchmark.** Run eval corpus under both loaders, capture metrics (P0-5).
4. **Phase D: Format matrix.** Verify 26/26 extension coverage (P0-6).
5. **Phase E: Decision.** Write ADR-005 with go/no-go recommendation (P0-7).

Phase A and B can overlap with fixture preparation; Phases C and D run in parallel; Phase E is gated on both.

## Critical Files

Files to be created or modified during the spike:

- `pyproject.toml`: add `docling` to optional extras
- `src/drover/loader.py`: add `DoclingLoader` class alongside existing `DocumentLoader`; extend `LoadedDocument` with `docling_doc: DoclingDocument | None` field
- `src/drover/config.py`: add `DROVER_LOADER` env var and `loader` config key
- `src/drover/cli.py`: add `--loader` flag to `classify` and `evaluate` commands
- `src/drover/classifier.py`: when `docling_doc` is present, prefer `doc.export_to_markdown()` over flat content for the prompt input around line 489
- `src/drover/nli_classifier.py`: when `docling_doc` is present, use `HybridChunker` instead of the current chunking strategies (around lines 339-349)
- `src/drover/extractors/base.py`: extend protocol with optional `structured_regions` parameter
- `src/drover/extractors/regex.py` and `extractors/llm.py`: when structured regions are provided, prefer them over flat-text regex
- `src/drover/metrics.py`: add `loader_latency_ms` and `loader_backend` fields (P1-2)
- `tests/test_loader.py`: add `DoclingLoader` fixtures and parity tests
- `tests/test_classifier.py`: assert markdown-with-headings reaches the prompt when `docling_doc` is set
- `tests/test_nli_classifier.py`: assert `HybridChunker` is selected when `docling_doc` is set
- `eval/baselines.md`: append Docling columns to comparison tables
- `docs/adr/005-docling-evaluation.md`: new ADR with spike report and decision

## Verification

End-to-end verification steps for the spike:

1. **Install:** `uv sync --extra docling` succeeds on macOS arm64 and Linux x86_64; `uv run python -c "from docling.document_converter import DocumentConverter; print('ok')"` prints `ok`.
2. **Smoke test:** `uv run drover classify eval/samples/<one-pdf> --loader docling --ai-provider ollama --ai-model llama3.2:latest` returns a valid `ClassificationResult`.
3. **Format matrix:** A new test in `tests/test_loader.py` parameterizes over every extension in `_SUPPORTED_EXTENSIONS` and asserts both loaders produce non-empty `content`. Failures are captured in the spike report, not silenced.
4. **Eval run:** `uv run drover evaluate eval/ground_truth.jsonl --loader docling` against three providers (Ollama gemma4:latest, Anthropic claude-haiku-4-5, NLI local) produces accuracy metrics that get pasted into `eval/baselines.md` next to the current numbers.
5. **Quality gates** (per `~/.claude/rules/python-dev.md`): `uv run ruff check src/ tests/`, `uv run mypy src/`, `uv run bandit -r src/`, `uv run pytest tests/ --cov=src` all pass with the new code.
6. **Decision artifact:** `docs/adr/005-docling-evaluation.md` exists, references the measured deltas, and ends with a clear "Decision: accept | reject | defer" line.

## References

- Drover repo: `/Users/ckrough/Code/open-source/drover`
- Current loader: `src/drover/loader.py`
- Eval corpus: `eval/ground_truth.jsonl` (80 documents)
- Existing baselines: `eval/baselines.md`
- NLI vs LLM research notes: [[nli-vs-llm-notes]]
- ADR-001 (chain-of-thought): `docs/adr/001-chain-of-thought-prompting.md`
- ADR-002 (privacy-first): `docs/adr/002-privacy-first-design.md`
- ADR-003 (NLI roadmap): `docs/adr/003-nli-classifier-roadmap.md`
- ADR-004 (local LLM as primary local path): `docs/adr/004-local-llm-as-primary-local-path.md`
- Docling docs: https://docling-project.github.io/docling/
- Docling repo: https://github.com/docling-project/docling
