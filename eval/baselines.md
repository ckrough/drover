---
title: Drover NLI Phase 2 Baselines
prepared_by: Claude (Opus 4.7)
updated: 2026-04-29T11:02:05-04:00
purpose: Phase 2 NLI accuracy baselines for the zero-shot DeBERTa classifier on the balanced 80-document eval corpus.
tags: []
aliases: []
---

# Drover NLI Phase 2 Baselines

Phase 2 zero-shot NLI baselines (`cross-encoder/nli-deberta-v3-base`) across all six `(chunk_strategy, aggregation)` combinations. Captured on a balanced 80-doc corpus (5+ per domain, 2+ categories per domain, 2+ doctypes per domain). These numbers replace the 3-doc and 33-doc snapshots in `docs/adr/003-nli-classifier-roadmap.md`. They will be folded into the ADR at PR-merge.

## Corpus

- 80 documents in `eval/samples/` (3 original + 77 synthetic).
- 16/16 canonical household-taxonomy domains, each with at least 5 documents, 2 categories, and 2 doctypes.
- 41 documents exceed the 512-token cross-encoder limit. The long-doc bias is intentional: long documents are where chunking strategies should differ most.
- All synthetic documents generated via Claude Sonnet 4.6 through `scripts/generate_eval_samples.py` with structured markdown templates per doctype (real tables, headings, signature blocks, line items).
- Ground truth: `eval/ground_truth.jsonl` (93 lines: 13 header + 80 entries).

## Phase 2 Baselines (2026-04-29, corpus = 80)

| Strategy | Domain | Category | Doctype | Vendor | Date |
|---|---|---|---|---|---|
| truncate / max | **3.8%** | 2.5% | 3.8% | 1.2% | 77.5% |
| sliding / max | 2.5% | 2.5% | 5.0% | 1.2% | 77.5% |
| sliding / mean | 2.5% | 2.5% | **6.2%** | 1.2% | 77.5% |
| sliding / weighted | 2.5% | 2.5% | **6.2%** | 1.2% | 77.5% |
| importance / max | 1.2% | 2.5% | 3.8% | 1.2% | 77.5% |
| importance / weighted | 2.5% | 2.5% | 5.0% | 1.2% | 77.5% |

## Comparison to 33-doc snapshot

| Metric | 33-doc best | 80-doc best | Delta |
|---|---|---|---|
| Domain | 3.0% (importance/weighted) | 3.8% (truncate) | +0.8pp, winner changed |
| Category | 0.0% (all combos) | 2.5% (all combos) | +2.5pp |
| Doctype | 12.1% (sliding/weighted) | 6.2% (sliding/mean+weighted) | -5.9pp |
| Date | 81.8% | 77.5% | -4.3pp |
| Vendor | 0.0% | 1.2% | +1.2pp |

## Observations

- **Doctype regressed on the larger corpus.** The 33-doc snapshot was over-indexed on a few easy doctypes (`manual`, `agreement`). Spreading to 16 doctypes across 16 domains drops accuracy 6pp. The new number is the honest baseline.
- **Truncate is now competitive on domain.** With more documents per domain, the leading 450-token window of most files is enough to identify the domain. The earlier "importance + weighted is the only domain-non-zero combo" result was corpus-specific, not architectural.
- **Sliding + mean/weighted still leads doctype.** 6.2% vs 3.8-5.0% for max-aggregations. Aggregating across chunks helps doctype classification more than domain or category.
- **Category is uniformly 2.5%** across all six combos. Per-category cues are not being captured by zero-shot NLI on this menu, regardless of chunking.
- **Date (77.5%) is the regex extractor.** It is invariant across NLI combos. The 4pp drop from 33-doc reflects more diverse date-format coverage in the new synthetic documents.
- **Vendor (1.2%)** is set by the metadata extractor, not the NLI head. Still effectively zero, as expected; exact vendor matches are a regression test, not a primary metric.
- Absolute accuracies remain low. The corpus is sized to differentiate strategies and surface real signal, not to validate zero-shot NLI for production. Phase 3+ work targets the gap.

## Reproducibility

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

Each row is one `drover evaluate` run with `DROVER_NLI_CHUNK_STRATEGY` and `DROVER_NLI_AGGREGATION` set to the column values. The bench script writes per-combo JSON to `${TMPDIR}/drover-phase2-bench/`. Note: stdout includes loader warnings before the JSON object, so parsers must scan to the first `{`.

## Generation Provenance

- Script: `scripts/generate_eval_samples.py` (with `--top-up` mode for coverage-aware expansion).
- Model: `claude-sonnet-4-6`.
- Concurrency: 5.
- Total cost: $0.43 (session-1, 30 docs, seed 42) + $0.75 (session-2, 47 docs, seed 43, `--top-up`) = $1.18 for 77 synthetic docs.
- Cache reads were 0; ephemeral cache requires >=1024-token system blocks, our system block is ~280 tokens.
- Per-doctype structural templates instruct Claude to use markdown headings, pipe tables, bullet lists, and signature blocks. The renderer (`_render_pdf`) parses these into reportlab Table/ListFlowable/Paragraph/HRFlowable elements.
