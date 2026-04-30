---
title: Drover LLM Baselines
prepared_by: Claude (Opus 4.7)
updated: 2026-04-29T13:32:27-04:00
purpose: LLM accuracy baseline on the balanced 80-document eval corpus.
tags: []
aliases: []
---

# Drover LLM Baselines

Baseline on a balanced 80-doc corpus (5+ per domain, 2+ categories per domain, 2+ doctypes per domain) for the supported LLM provider:

- **LLM**: `gemma4:latest` via local Ollama (single column).

These numbers supersede the 3-doc and 33-doc snapshots referenced historically in `docs/adr/003-nli-classifier-roadmap.md`.

## Corpus

- 80 documents in `eval/samples/` (3 original + 77 synthetic).
- 16/16 canonical household-taxonomy domains, each with at least 5 documents, 2 categories, and 2 doctypes.
- 41 documents exceed 512 tokens in the synthetic generator's tokenizer. The long-doc bias is intentional: long documents stress the page-sampling strategies in `src/drover/sampling.py` more than short ones.
- All synthetic documents generated via Claude Sonnet 4.6 through `scripts/generate_eval_samples.py` with structured markdown templates per doctype (real tables, headings, signature blocks, line items).
- Ground truth: `eval/ground_truth.jsonl` (93 lines: 13 header + 80 entries).

## LLM baseline (2026-04-29, corpus = 80)

| Provider | Model | Domain | Category | Doctype | Vendor | Date |
|---|---|---|---|---|---|---|
| ollama | gemma4:latest | **87.5%** | **40.0%** | **86.2%** | **78.8%** | **88.8%** |

Single run, sequential (concurrency=1), ~30 minutes wallclock on M-series Mac. Zero classification errors out of 80 documents.

## LLM observations

- **Gemma4 dominates every classification axis** that prior NLI baselines covered. Even category, the worst-performing axis at 40%, is roughly an order of magnitude above what the (now-removed) zero-shot NLI path achieved on the same corpus.
- **Vendor and date pop up because the LLM extracts them directly.** Drover's LLM path uses `with_structured_output()` to fill `RawClassification`, so the model sees the document text and writes vendor/date into the JSON in a single pass.
- **Cost: 0.** Local Ollama, no API spend. Wallclock ~30 min on M-series for 80 docs sequential. Per-doc cost in time is the binding constraint.
- **Category remains the hardest axis** at 40%. Per-category cues in the taxonomy menu are subtler than domain or doctype distinctions. The Docling spike (ADR-005) tested whether a structure-aware loader would lift category and concluded no on this corpus.

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

Note: stdout includes loader warnings before the JSON object, so parsers must scan to the first `{`.

## Generation Provenance

- Script: `scripts/generate_eval_samples.py` (with `--top-up` mode for coverage-aware expansion).
- Model: `claude-sonnet-4-6`.
- Concurrency: 5.
- Total cost: $0.43 (session-1, 30 docs, seed 42) + $0.75 (session-2, 47 docs, seed 43, `--top-up`) = $1.18 for 77 synthetic docs.
- Cache reads were 0; ephemeral cache requires >=1024-token system blocks, our system block is ~280 tokens.
- Per-doctype structural templates instruct Claude to use markdown headings, pipe tables, bullet lists, and signature blocks. The renderer (`_render_pdf`) parses these into reportlab Table/ListFlowable/Paragraph/HRFlowable elements.
