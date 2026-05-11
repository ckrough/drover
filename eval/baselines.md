---
title: Drover LLM Baselines
prepared_by: Claude (Opus 4.7)
updated: 2026-05-10T21:47:38-04:00
purpose: LLM accuracy baseline on the balanced 80-document eval corpus.
tags: []
aliases: []
---

# Drover LLM Baselines

Baseline on a balanced 80-doc corpus (5+ per domain, 2+ categories per domain, 2+ doctypes per domain) for the supported LLM provider:

- **LLM**: `gemma4:latest` via local Ollama (single column).

These numbers supersede the 3-doc and 33-doc snapshots referenced historically in `docs/adr/003-nli-classifier-roadmap.md`.

## Corpus

- 80 documents in `eval/samples/synthetic/` (3 original + 77 synthetic).
- 16/16 canonical household-taxonomy domains, each with at least 5 documents, 2 categories, and 2 doctypes.
- 41 documents exceed 512 tokens in the synthetic generator's tokenizer. The long-doc bias is intentional: long documents stress the page-sampling strategies in `src/drover/sampling.py` more than short ones.
- All synthetic documents generated via Claude Sonnet 4.6 through `scripts/generate_eval_samples.py` with structured markdown templates per doctype (real tables, headings, signature blocks, line items).
- Ground truth: `eval/ground_truth/synthetic.jsonl` (93 lines: 13 header + 80 entries).

## LLM baseline (2026-05-10, commit f804c3c, corpus = 80)

| Provider | Model | Loader | Domain | Category | Doctype | Vendor | Date | Entity |
|---|---|---|---|---|---|---|---|---|
| ollama | gemma4:latest | docling (ocrmac) | **86.2%** | **61.2%** | **91.2%** | **91.2%** | **90.0%** | **70.0%** |

Single run, sequential (concurrency=1), ~24 minutes wallclock on M-series Mac. Zero classification errors out of 80 documents. Entity accuracy is over the 20 entity-labelled documents in `eval/ground_truth/synthetic.jsonl`.

Run directory: `eval/runs/baseline-20260510-212126/`.

### Deltas from previous baseline (2026-04-29)

| Metric | 2026-04-29 | 2026-05-10 (f804c3c) | Delta |
|---|---|---|---|
| Domain | 87.5% | 86.2% | -1.3 pp |
| Category | 40.0% | 61.2% | +21.2 pp |
| Doctype | 86.2% | 91.2% | +5.0 pp |
| Vendor | 78.8% | 91.2% | +12.4 pp |
| Date | 88.8% | 90.0% | +1.2 pp |

Drivers of the improvement: Docling full-page OCR (ADR-005, ADR-006), Round 4 taxonomy plural-doctype refactor, taxonomy demotions (correspondence, reference, hierarchy), lifestyle/entertainment categories, dropping the `personal` domain, and entity-field extraction.

## LLM observations

- **Category lifts from 40% to 61.2%** as the taxonomy maturation work since 2026-04-29 lands: Round 4 plural-doctype refactor, correspondence/reference/hierarchy demotions, lifestyle/entertainment additions, and the `personal` domain drop.
- **Vendor and date pop up because the LLM extracts them directly.** Drover's LLM path uses `with_structured_output()` to fill `RawClassification`, so the model sees the document text and writes vendor/date into the JSON in a single pass. Vendor rises from 78.8% to 91.2% with Docling full-page OCR feeding cleaner text into the prompt.
- **Cost: 0.** Local Ollama, no API spend. Wallclock ~24 min on M-series for 80 docs sequential. Per-doc cost in time is the binding constraint.
- **Category remains the hardest axis** at 61.2%. Per-category cues in the taxonomy menu are subtler than domain or doctype distinctions; further gains likely come from prompt tuning or per-category exemplars rather than loader changes.
- **Entity (70.0%)** is a new field introduced with ADR-007. Six of the twenty entity-labelled documents miss because of `unknown` literal emission, traveller-name leakage on itineraries, and a two-pet receipt where the model concatenates both names; all three are tractable follow-ups in the prompt or the schema normalizer.

## Reproducibility

LLM baseline:
```bash
env -u ALL_PROXY -u all_proxy -u FTP_PROXY -u GRPC_PROXY \
  uv run drover evaluate \
    --ground-truth eval/ground_truth/synthetic.jsonl \
    --documents-dir eval/samples/synthetic \
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
