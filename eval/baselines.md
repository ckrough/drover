---
title: Drover NLI Phase 2 Baselines
prepared_by: Claude (Opus 4.7)
updated: 2026-04-28T14:15:00-04:00
purpose: Interim accuracy baselines for the Phase 1+2 NLI classifier on the expanded eval corpus, captured before PR landing so regressions can be measured against a real signal.
tags: []
aliases: []
---

# Drover NLI Phase 2 Baselines

Interim accuracy baselines for the zero-shot NLI classifier (`cross-encoder/nli-deberta-v3-base`) across all six `(chunk_strategy, aggregation)` combinations introduced in Phase 2. Captured on the expanded eval corpus before the PR lands so Phase 3+ work has a measurable starting point. These numbers replace the uninterpretable 3-doc baselines documented in `docs/adr/003-nli-classifier-roadmap.md` under `### Phase 2 Baselines (2026-04-27)`. They will be folded into the ADR at PR-merge.

## Corpus

- 33 documents in `eval/samples/` (3 original + 30 newly generated).
- 16/16 canonical household-taxonomy domains represented.
- 16 documents exceed the 512-token cross-encoder limit (target was 5).
- All 30 new documents synthetic, generated via Claude Sonnet 4.6 through `scripts/generate_eval_samples.py` with structured markdown templates per doctype (real tables, headings, signature blocks, line items).
- Ground truth: `eval/ground_truth.jsonl` (46 lines: 13 header + 33 entries).

## Phase 2 Baselines (2026-04-28, corpus = 33)

| Strategy | Domain | Category | Doctype | Vendor | Date |
|---|---|---|---|---|---|
| truncate / max | 0.0% | 0.0% | 9.1% | 0.0% | 81.8% |
| sliding / max | 0.0% | 0.0% | 9.1% | 0.0% | 81.8% |
| sliding / mean | 0.0% | 0.0% | 12.1% | 0.0% | 81.8% |
| sliding / weighted | 0.0% | 0.0% | 12.1% | 0.0% | 81.8% |
| importance / max | 0.0% | 0.0% | 9.1% | 0.0% | 81.8% |
| importance / weighted | **3.0%** | 0.0% | **12.1%** | 0.0% | 81.8% |

## Observations

- The expanded corpus differentiates strategies. The 3-doc set tied every combination at 0/0/33% domain/category/doctype; this set separates them.
- **weighted aggregation** outperforms max and mean on doctype (12.1% vs 9.1%), under both sliding and importance chunkers.
- **importance + weighted** is the only combo that produces a non-zero domain hit (3.0%, 1/33). The default truncate strategy returns zero.
- Date accuracy (81.8%) reflects the regex extractor, not the NLI head. It is stable across all six combos.
- Vendor accuracy is zero across all combos because the vendor field is set by an extractor that this evaluation pipeline does not exercise as zero-shot NLI.
- Absolute accuracies are still very low. The corpus exists to make differences measurable, not to validate zero-shot NLI as production-ready. Phase 3+ work targets the gap.

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

Each row is one `drover evaluate` run with `DROVER_NLI_CHUNK_STRATEGY` and `DROVER_NLI_AGGREGATION` set to the column values. The bench script writes per-combo JSON to `${TMPDIR}/drover-phase2-bench/`.

## Generation Provenance

- Script: `scripts/generate_eval_samples.py`
- Model: `claude-sonnet-4-6`
- Concurrency: 5
- Cost: $0.43 for 30 docs (cache reads were 0; ephemeral cache requires ≥1024-token system blocks and our system block is ~280 tokens).
- Seed: 42 (deterministic coverage plan; vendor/date/amount randomized within domain pools).
- Per-doctype structural templates instruct Claude to use markdown headings, pipe tables, bullet lists, and signature blocks. The renderer (`_render_pdf`) parses these into reportlab Table/ListFlowable/Paragraph/HRFlowable elements.
