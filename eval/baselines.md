---
title: Drover Phase 2 Baselines
prepared_by: Claude (Opus 4.7)
updated: 2026-04-29T13:32:27-04:00
purpose: Phase 2 LLM and NLI accuracy baselines on the balanced 80-document eval corpus.
tags: []
aliases: []
---

# Drover Phase 2 Baselines

Phase 2 baselines on a balanced 80-doc corpus (5+ per domain, 2+ categories per domain, 2+ doctypes per domain) for two providers:

- **LLM**: `gemma4:latest` via local Ollama (single column).
- **NLI**: `cross-encoder/nli-deberta-v3-base` zero-shot, all six `(chunk_strategy, aggregation)` combinations.

These numbers replace the 3-doc and 33-doc snapshots in `docs/adr/003-nli-classifier-roadmap.md`. They will be folded into the ADR at PR-merge.

## Corpus

- 80 documents in `eval/samples/` (3 original + 77 synthetic).
- 16/16 canonical household-taxonomy domains, each with at least 5 documents, 2 categories, and 2 doctypes.
- 41 documents exceed the 512-token cross-encoder limit. The long-doc bias is intentional: long documents are where chunking strategies should differ most.
- All synthetic documents generated via Claude Sonnet 4.6 through `scripts/generate_eval_samples.py` with structured markdown templates per doctype (real tables, headings, signature blocks, line items).
- Ground truth: `eval/ground_truth.jsonl` (93 lines: 13 header + 80 entries).

## LLM baseline (2026-04-29, corpus = 80)

| Provider | Model | Domain | Category | Doctype | Vendor | Date |
|---|---|---|---|---|---|---|
| ollama | gemma4:latest | **87.5%** | **40.0%** | **86.2%** | **78.8%** | **88.8%** |

Single run, sequential (concurrency=1), ~30 minutes wallclock on M-series Mac. Zero classification errors out of 80 documents.

## NLI baselines (2026-04-29, corpus = 80)

| Strategy | Domain | Category | Doctype | Vendor | Date |
|---|---|---|---|---|---|
| truncate / max | **3.8%** | 2.5% | 3.8% | 1.2% | 77.5% |
| sliding / max | 2.5% | 2.5% | 5.0% | 1.2% | 77.5% |
| sliding / mean | 2.5% | 2.5% | **6.2%** | 1.2% | 77.5% |
| sliding / weighted | 2.5% | 2.5% | **6.2%** | 1.2% | 77.5% |
| importance / max | 1.2% | 2.5% | 3.8% | 1.2% | 77.5% |
| importance / weighted | 2.5% | 2.5% | 5.0% | 1.2% | 77.5% |

## LLM vs NLI gap

| Metric | NLI best | Gemma4 | Gap |
|---|---|---|---|
| Domain | 3.8% | 87.5% | +83.7pp |
| Category | 2.5% | 40.0% | +37.5pp |
| Doctype | 6.2% | 86.2% | +80.0pp |
| Vendor | 1.2% | 78.8% | +77.6pp |
| Date | 77.5% | 88.8% | +11.3pp |

The LLM is roughly an order of magnitude more accurate on every classification axis. Date is closer because the NLI side relies on the same regex extractor; the gap there is whatever the LLM's date interpretation adds. Category remains the hardest axis even for the LLM (40%) — per-category cues in the taxonomy menu are subtler than domain or doctype distinctions.

## NLI: comparison to 33-doc snapshot

| Metric | 33-doc best | 80-doc best | Delta |
|---|---|---|---|
| Domain | 3.0% (importance/weighted) | 3.8% (truncate) | +0.8pp, winner changed |
| Category | 0.0% (all combos) | 2.5% (all combos) | +2.5pp |
| Doctype | 12.1% (sliding/weighted) | 6.2% (sliding/mean+weighted) | -5.9pp |
| Date | 81.8% | 77.5% | -4.3pp |
| Vendor | 0.0% | 1.2% | +1.2pp |

## NLI observations

- **Doctype regressed on the larger corpus.** The 33-doc snapshot was over-indexed on a few easy doctypes (`manual`, `agreement`). Spreading to 16 doctypes across 16 domains drops accuracy 6pp. The new number is the honest baseline.
- **Truncate is now competitive on domain.** With more documents per domain, the leading 450-token window of most files is enough to identify the domain. The earlier "importance + weighted is the only domain-non-zero combo" result was corpus-specific, not architectural.
- **Sliding + mean/weighted still leads doctype.** 6.2% vs 3.8-5.0% for max-aggregations. Aggregating across chunks helps doctype classification more than domain or category.
- **Category is uniformly 2.5%** across all six combos. Per-category cues are not being captured by zero-shot NLI on this menu, regardless of chunking.
- **Date (77.5%) is the regex extractor.** It is invariant across NLI combos. The 4pp drop from 33-doc reflects more diverse date-format coverage in the new synthetic documents.
- **Vendor (1.2%)** is set by the metadata extractor, not the NLI head. Still effectively zero, as expected; exact vendor matches are a regression test, not a primary metric.
- Absolute accuracies remain low. The corpus is sized to differentiate strategies and surface real signal, not to validate zero-shot NLI for production. Phase 3+ work targets the gap.

## LLM observations

- **Gemma4 dominates every axis.** Even category, the worst-performing axis, is 16x the best NLI score.
- **Vendor and date pop up because the LLM extracts them directly.** Drover's LLM path uses `with_structured_output()` to fill `RawClassification`, so the model sees the document text and writes vendor/date into the JSON. The NLI path runs a separate regex extractor that doesn't read the surrounding context.
- **Cost: 0.** Local Ollama, no API spend. Wallclock ~30 min on M-series for 80 docs sequential. Per-doc cost in time is the binding constraint.
- **Implication for Phase 3.** Closing the LLM-NLI gap with prompt/hypothesis tuning is unlikely to recover 80pp on doctype or 78pp on vendor — those gaps are about the model class, not the chunking strategy. Fine-tuning (Phase 5+ in ADR-003) is the credible path to NLI parity.

## Reproducibility

LLM baseline:
```bash
env -u ALL_PROXY -u all_proxy -u FTP_PROXY -u GRPC_PROXY \
  uv run drover evaluate \
    --ground-truth eval/ground_truth.jsonl \
    --documents-dir eval/samples \
    --ai-provider ollama \
    --ai-model gemma4:latest \
    --output json \
    --log quiet
```

NLI baselines:
```bash
env -u ALL_PROXY -u all_proxy -u FTP_PROXY -u GRPC_PROXY \
  uv run drover evaluate \
    --ground-truth eval/ground_truth.jsonl \
    --documents-dir eval/samples \
    --ai-provider nli_local \
    --output json \
    --log quiet

bash /tmp/claude/drover-phase2-bench.sh
```

Each NLI row is one `drover evaluate` run with `DROVER_NLI_CHUNK_STRATEGY` and `DROVER_NLI_AGGREGATION` set to the column values. The bench script writes per-combo JSON to `${TMPDIR}/drover-phase2-bench/`. Note: stdout includes loader warnings before the JSON object, so parsers must scan to the first `{`.

## Generation Provenance

- Script: `scripts/generate_eval_samples.py` (with `--top-up` mode for coverage-aware expansion).
- Model: `claude-sonnet-4-6`.
- Concurrency: 5.
- Total cost: $0.43 (session-1, 30 docs, seed 42) + $0.75 (session-2, 47 docs, seed 43, `--top-up`) = $1.18 for 77 synthetic docs.
- Cache reads were 0; ephemeral cache requires >=1024-token system blocks, our system block is ~280 tokens.
- Per-doctype structural templates instruct Claude to use markdown headings, pipe tables, bullet lists, and signature blocks. The renderer (`_render_pdf`) parses these into reportlab Table/ListFlowable/Paragraph/HRFlowable elements.

## Format Coverage Matrix (Docling Spike, prof-dt6)

The full per-extension matrix lives at `eval/format_matrix.md`. Rebuild with:

```bash
uv run python scripts/format_matrix.py --write
```

Summary across the 24 buildable extensions (the three legacy `.doc/.xls/.ppt` are SKIPped — neither loader handles them without a Microsoft Office toolchain):

- 9 PASS (both loaders extract): `.csv`, `.docx`, `.htm`, `.html`, `.md`, `.pdf`, `.pptx`, `.tsv`, `.txt`, `.xlsx`.
- 7 GAIN (docling extracts where unstructured does not in this environment, primarily image OCR): `.bmp`, `.gif`, `.jpeg`, `.jpg`, `.png`, `.tif`, `.tiff`.
- 3 REGRESS (unstructured extracts, docling does not): `.eml`, `.epub`, `.rtf`. Captured in `tests/test_format_matrix.py::KNOWN_REGRESSIONS` for ADR-005.
- 1 FAIL (neither loader): `.odt`.

Per spike P0-6, REGRESS rows are blocking input for the go/no-go call (prof-nzl).
