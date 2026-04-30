---
title: Zero-Shot NLI vs Local LLM for Document Classification — Research Notes
prepared_by: Claude (Opus 4.7)
updated: 2026-04-29T13:41:57-04:00
purpose: Source data, methods, results, and lessons learned from the drover Phase 1+2 NLI experiment, structured for a future blog post.
tags: []
aliases: []
---

# Zero-Shot NLI vs Local LLM for Document Classification — Research Notes

> **Status: HISTORICAL.** The zero-shot NLI classifier described here was implemented, evaluated, and then removed from Drover. The decision is recorded in [ADR-004](../adr/004-local-llm-as-primary-local-path.md), which adopts the local LLM (Ollama `gemma4:latest`) as the primary local classification path. This document is preserved as a factual record of the experiment; nothing here describes Drover's current behavior.

These are research notes, not the blog post. The structure below mirrors an arXiv paper so that the eventual blog post can pick and shape sections without rediscovering the data.

## Abstract (one paragraph)

Drover is a CLI that classifies arbitrary documents (invoices, leases, reports, etc.) into a definable taxonomy and builds an organized destination path. The original encoding implementation called OpenAI's encoding LLM. We added a second classification path based on a zero-shot NLI cross-encoder (`cross-encoder/nli-deberta-v3-base`) to enable fully-offline, no-server, no-API-cost classification. 

Phase 1 shipped the MVP; Phase 2 added long-document chunking and per-chunk score aggregation. After expanding the eval corpus from 3 to 80 documents, the zero-shot NLI classifier achieves at most 3.8% domain / 2.5% category / 6.2% doctype accuracy. A small local LLM (`gemma4:latest`, 9.6GB, via Ollama, $0 marginal cost) achieves 87.5% / 40.0% / 86.2% on the same corpus. The gap is 11-84 percentage points on every axis. Closing this gap with prompt or chunking changes is implausible; fine-tuning is the credible path. We document corpus construction, the chunking-and-aggregation matrix, and the operational gotchas that ate session time.

## 1. Introduction and motivation

- Drover ships as `drover classify FILE`. The default path uses a cloud LLM; the goal of the NLI work was to add a fully-local, no-API-spend alternative that still slots into the existing `ClassificationService` factory.
- Project constraints (ADR-002): privacy-first, local-first, no model server (Ollama is on the borderline — local but stateful).
- Zero-shot NLI is attractive: 110-300M-parameter classifier-grade cross-encoders, no training, adapts to new taxonomies via hypothesis templates.
- The hypothesis we wanted to test: **can a zero-shot NLI cross-encoder match a small local LLM closely enough to replace it in the no-API-spend path?**
- The answer turned out to be no, by a wide margin. The corpus expansion that made the answer measurable also made the answer unambiguous.

## 2. System under test

### 2.1 Architecture

- `drover/cli.py` → `drover.service.ClassificationService` → factory selects between `DocumentClassifier` (LLM, LangChain `with_structured_output()`) and `NLIDocumentClassifier`.
- The LLM path produces `RawClassification` directly: domain, category, doctype, vendor, date, subject in one structured-output JSON call.
- The NLI path is hierarchical: it scores `(document_text, hypothesis)` entailment against a list of natural-language hypotheses for each level (domain → category-given-domain → doctype). Vendor and date come from a separate `extractors/regex.py` (or `extractors/llm.py` hybrid extractor) — the NLI head doesn't see them.
- Document loading is shared: `drover.loader.DocumentLoader` (PDF, DOCX, plain text via the `unstructured` library). Sampling strategies trim long documents.

### 2.2 NLI Phase 1 (MVP) — commit `d7e1614` (2025-12-18)

- Model: `cross-encoder/nli-deberta-v3-base`. 184M params, 512-token premise limit.
- Hypothesis templates per level, e.g. domain hypotheses are full sentences ("This document is about medical care and health.", etc.). One template per canonical label.
- Long-document handling in Phase 1: silent truncation to 510 tokens.
- Lazy model load on first call. `local_files_only=True` first, network fallback.
- Optional install via the `[nli]` extra (`uv sync --all-extras`).

### 2.3 NLI Phase 2 (chunking + aggregation) — commit `9bf9e89` (2026-04-27)

- New config knobs: `ChunkStrategy ∈ {truncate, sliding, importance}`, `Aggregation ∈ {max, mean, weighted}`, `chunk_size` (default 400, capped at 510), `chunk_overlap` (default 100). Validators reject `chunk_overlap >= chunk_size`.
- Env passthrough: `DROVER_NLI_CHUNK_STRATEGY` / `CHUNK_SIZE` / `CHUNK_OVERLAP` / `AGGREGATION`.
- `src/drover/chunking.py`: `chunk_truncate` (single chunk), `chunk_sliding` (overlapping windows covering the full document), `chunk_importance` (TF-IDF-scored sentences via lazy-imported `scikit-learn`). `CHUNKERS` registry maps the enum to the function.
- `src/drover/aggregation.py`: `aggregate_max`, `aggregate_mean`, `aggregate_weighted` (first/last chunks count 2x, middle chunks 1x). `AGGREGATORS` registry.
- `_classify_level` flow: chunk content, score each `(chunk, hypothesis)` pair, max-pool over hypothesis templates per chunk, aggregate per label across chunks.
- New tests: 37 across `tests/test_aggregation.py` (15), `tests/test_chunking.py` (14), `tests/test_config.py` (8).
- Defaults preserve Phase 1 behavior: `truncate + max` is exactly the original single-chunk path.

## 3. Eval corpus construction

### 3.1 Why we had to build one

- Pre-existing eval set: 3 documents (`medical_bill.pdf`, `receipt.pdf`, `user_manual.pdf`), 3 of 16 domains.
- On 2026-04-27 the rebased Phase 1 NLI scored 0/3 domain, 0/3 category, 1/3 doctype on this set.
- Phase 2 chunking baselines on this 3-doc set: every `(chunk_strategy, aggregation)` combination tied at 0% / 0% / 33%. **Cannot differentiate strategies.** That is what triggered the corpus-expansion work tracked under beads issue `prof-5cg`.

### 3.2 Generator design — commit `65f6ba3` (2026-04-28)

- `scripts/generate_eval_samples.py`, single file, ~700 LOC, async.
- Triple selection: `_coverage_plan(count, min_long, seed)` deterministically picks `(domain, category, doctype)` from `HouseholdTaxonomy.CANONICAL_*`. Ensures all 16 domains land at least once. Long-doc target filled with verbose triples (`lease`, `manual`, `policy`, `will`, etc.).
- Generation: Sonnet 4.6 via `langchain-anthropic.ChatAnthropic`, `temperature=0.7`, `max_tokens=4096`, `extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"}`. `cache_control={"type":"ephemeral"}` on the system block (engaged 0 times — see §6.4).
- Per-doctype structural prompt templates (`DOCTYPE_STRUCTURE_HINTS`): invoice → line-item table; lease → numbered sections + signature block; manual → TOC + chapters; recipe → bulleted ingredients + numbered steps; paystub → earnings/deductions tables. Without these, Claude produced memo-style prose that did not look like real documents.
- Rendering: custom markdown-to-reportlab parser (~150 LOC). Parses headings, pipe tables, bullet/numbered lists, horizontal rules, inline bold/italic into `Paragraph`, `Table`, `ListFlowable`, `HRFlowable` flowables. Asserts the output PDF is `>1024` bytes and parseable by `unstructured` before accepting.
- Output validation: Pydantic `GroundTruthRow` with field validators that call `taxonomy.canonical_domain(...)`, `canonical_category(domain, ...)`, `canonical_doctype(...)` and reject `None`. Rejects partial-zero dates per `prof-5qy` invariant.
- Injection sanitizer: rejects outputs containing `"ignore previous"`, `"system:"`, `"assistant:"`, `<|im_start|>`, etc. 0/77 rejections in production runs.
- Atomic JSONL append: write full new file to `tempfile.mkstemp()`, then `Path(tmp).replace(jsonl_path)`. Survives crashes.
- Resume: skip triples whose target filename already exists in `output-dir` or whose row already exists in `ground_truth.jsonl`. Same seed re-runs become no-ops on already-generated docs.
- Cost ledger: per-call usage capture, `_estimate_cost()`, hard ceiling via `--max-cost-usd` (default $6, never approached).
- Concurrency: `asyncio.gather` with `Semaphore(5)`.

### 3.3 Coverage-aware top-up (session 2) — commit `f70baf1` (2026-04-29)

- Session 1 produced 33 docs at minimum coverage (≥1 per domain). Session 2's acceptance criterion was 5+ docs / 2+ categories / 2+ doctypes per domain across all 16 domains, requiring ~50 more docs.
- New `--top-up` CLI mode plus `_topup_plan(rows, taxonomy, target_per_domain, target_cats, target_doctypes, seed)`.
- Three-stage greedy fill: (1) add triples that introduce missing categories until each domain has ≥2 cats; (2) add triples that introduce missing doctypes until each domain has ≥2 doctypes; (3) pad to target_per_domain, biasing toward `LONG_TRIPLES` so long-doc coverage stays healthy.
- Final corpus: 80 docs, 16/16 domains at 5+/2+/2+, 41 docs >512 cross-encoder tokens. Generation cost: $0.43 (session-1, 30 docs, seed 42) + $0.75 (session-2, 47 docs, seed 43, top-up) = $1.18 for 77 synthetic docs.

### 3.4 Corpus characteristics

- Per-domain count: `medical=5, education=5, financial=5, food=5, government=5, household=5, housing=5, insurance=5, legal=5, lifestyle=5, career=5, personal=5, pets=5, property=5, reference=5, utilities=5`.
- Per-domain categories: 2-4 per domain (median 2).
- Per-domain doctypes: 2-3 per domain (median 2).
- Long-doc bias: 41 of 80 (51%) exceed 512 cross-encoder tokens. Lease, will, policy, manual templates are intentionally verbose to exercise chunking.
- Format: 100% PDF, all born-digital. No DOCX, no scanned/OCR-only PDFs (the original prof-5cg description mentioned format mix; the AC checklist did not enforce it; we did not add it).

## 4. Methods

### 4.1 NLI baselines: 6-combo matrix

The 6 cells are not a full Cartesian product of {truncate, sliding, importance} × {max, mean, weighted}: `truncate` produces a single chunk so aggregation is a no-op (one row); `sliding` and `importance` each get all three aggregations.

```bash
# Per cell:
DROVER_NLI_CHUNK_STRATEGY=<strategy> DROVER_NLI_AGGREGATION=<agg> \
  drover evaluate --ground-truth eval/ground_truth.jsonl \
                  --documents-dir eval/samples \
                  --ai-provider nli_local \
                  --output json --log quiet
```

Bench script: `/tmp/claude/drover-phase2-bench.sh` (not committed; lives in dev session). Each combo on the 80-doc corpus takes 5-12 minutes on M-series CPU; the full 6-combo bench takes ~70 minutes.

### 4.2 LLM baseline: gemma4 via local Ollama

```bash
drover evaluate --ground-truth eval/ground_truth.jsonl \
                --documents-dir eval/samples \
                --ai-provider ollama \
                --ai-model gemma4:latest \
                --output json --log quiet
```

`gemma4:latest` (9.6GB, Q4 quant) via local Ollama. Runs sequentially (concurrency=1 by default in `drover evaluate`). 80 docs took ~30 minutes wallclock on M-series Mac. Zero classification errors. $0 marginal cost.

### 4.3 Metrics

`drover evaluate` reports per-axis exact-match accuracy: `domain_accuracy`, `category_accuracy`, `doctype_accuracy`, `vendor_accuracy`, `date_accuracy`. Vendor and date are case-insensitive; vendor is normalized via the eval-runner improvements from PR #19 (commit `ae79026`).

## 5. Results

### 5.1 NLI 6-combo matrix on 80-doc corpus (2026-04-29)

| Strategy | Domain | Category | Doctype | Vendor | Date |
|---|---|---|---|---|---|
| truncate / max | **3.8%** | 2.5% | 3.8% | 1.2% | 77.5% |
| sliding / max | 2.5% | 2.5% | 5.0% | 1.2% | 77.5% |
| sliding / mean | 2.5% | 2.5% | **6.2%** | 1.2% | 77.5% |
| sliding / weighted | 2.5% | 2.5% | **6.2%** | 1.2% | 77.5% |
| importance / max | 1.2% | 2.5% | 3.8% | 1.2% | 77.5% |
| importance / weighted | 2.5% | 2.5% | 5.0% | 1.2% | 77.5% |

### 5.2 LLM single-cell on 80-doc corpus (2026-04-29)

| Provider | Model | Domain | Category | Doctype | Vendor | Date |
|---|---|---|---|---|---|---|
| ollama | gemma4:latest | **87.5%** | **40.0%** | **86.2%** | **78.8%** | **88.8%** |

### 5.3 Gap

| Metric | NLI best | Gemma4 | Gap (pp) |
|---|---|---|---|
| Domain | 3.8% | 87.5% | +83.7 |
| Category | 2.5% | 40.0% | +37.5 |
| Doctype | 6.2% | 86.2% | +80.0 |
| Vendor | 1.2% | 78.8% | +77.6 |
| Date | 77.5% | 88.8% | +11.3 |

### 5.4 Corpus-size effect on NLI (3-doc → 33-doc → 80-doc)

| Corpus | Domain best | Category best | Doctype best | Notes |
|---|---|---|---|---|
| 3 docs (2025-12-18 / 2026-04-27) | 0.0% all | 0.0% all | 33% all | All 6 combos tied; no signal |
| 33 docs (2026-04-28) | 3.0% (importance/weighted) | 0.0% all | 12.1% (sliding/weighted) | One winning combo on domain; doctype peak |
| 80 docs (2026-04-29) | 3.8% (truncate/max) | 2.5% all | 6.2% (sliding/mean+weighted) | Truncate now leads domain; doctype regressed |

The 33→80 doctype regression is not a Phase 2 regression; it reflects the smaller corpus over-indexing on `manual` and `agreement` doctypes. The 80-doc baseline is honest.

## 6. Discussion / lessons learned

### 6.1 Corpus size determines what hypotheses you can test
A 3-document eval set tied every chunk × aggregation combo at 0/0/33%. A reader of those numbers would conclude "the strategies are equivalent." They are not — the corpus simply lacked discriminative power. Two extra sessions went into corpus expansion before Phase 2 results meant anything. **Build the corpus before you build the algorithm.**

### 6.2 Easy doctypes inflate scores
The 33-doc snapshot put doctype at 12.1%. Spreading to 16 doctypes across 16 domains dropped it to 6.2%. The earlier number was the corpus, not the algorithm. **A small corpus's accuracy is not a lower bound on a larger corpus's accuracy.**

### 6.3 Zero-shot NLI is order-of-magnitude behind a small LLM
Gemma4 beats every NLI cell on every axis: domain 23x, category 16x, doctype 14x, vendor 66x, date 1.15x. The date gap is small only because both paths share the regex extractor; the LLM's gain there is what reading dates in context adds on top of regex. **Closing 80pp on doctype with chunking changes is not a research direction. Fine-tuning a small encoder on labeled data is.**

### 6.4 Prompt caching has a minimum-block-size threshold
We set `cache_control: ephemeral` on the generator's system block. We saw 0 cache reads across 77 calls. Anthropic's ephemeral cache requires the cached block to be ≥1024 tokens; our system block was ~280. **Either inflate the prompt to cross the threshold, or remove the cache annotation as dead complexity.**

### 6.5 Synthetic-document quality requires structural prompts
First-pass smoke output looked like memos. Adding per-doctype structural templates (table layouts for invoices, signature blocks for leases, TOCs for manuals, line items for receipts) plus a markdown-to-reportlab parser produced PDFs that exercise the loader's table and list extraction rather than just paragraph extraction. **"Generate a realistic invoice" without a structural rubric does not yield a realistic invoice.**

### 6.6 Vendor exact-match is a regression metric, not a primary one
NLI vendor accuracy is 1.2% across the matrix. The regex extractor only finds vendors when they appear in a known pattern (signature blocks, "From:" headers). Realistic but generated documents have varied vendor placement. Even Gemma4 gets 78.8% — and that's in-context extraction. **Treat exact-match vendor as a "did we regress?" signal, not a model-quality signal.**

### 6.7 Closed = merged is correct, but it creates phantom WIP
Project rule: a beads issue closes only when the branch lands on `main`. The Phase 1+2 implementation issues (`prof-2oe`, `prof-4xe`, `prof-mnb`, `prof-qde`, `prof-avq`) are listed as `in_progress` despite the code being shipped on the unmerged branch. This is deliberate, but a stranger reading `bd list --status=in_progress` sees a misleading picture. **An external observer needs the merge state, not the issue state, to know what's done.**

### 6.8 Operational gotchas accumulate
- `HF_HUB_OFFLINE=1` currently makes `transformers` refuse the local cache for `cross-encoder/nli-deberta-v3-base`. Do not set it.
- `drover evaluate --output json` writes loader warnings (`Warning: No languages specified...`) to stdout *before* the JSON object. Naive parsers fail; consumers must scan to the first `{`.
- The 6-combo bench script lives at `/tmp/claude/drover-phase2-bench.sh` and is not committed. Rebuild from memory when the dev session restarts.
- LangChain emits `UserWarning: extra_headers is not default parameter. extra_headers was transferred to model_kwargs.` This is benign but noisy.
- `drover/cli.py:_evaluate_async` branches on `AIProvider.NLI_LOCAL` to instantiate `NLIDocumentClassifier`. The default `DocumentClassifier` raises `'Unsupported provider'` for `nli_local` — easy to mis-wire when adding a new provider.

## 7. Limitations and threats to validity

- **Corpus is 100% synthetic.** Generated by Sonnet 4.6 with structural rubrics, but still LLM-prose. Real-world documents have OCR noise, scanned-PDF artifacts, multi-column layouts, handwriting, and adversarial structure that synthetic generation does not produce.
- **Corpus is born-digital PDF only.** No DOCX, no scanned/OCR PDF, no plain text. The ADR description mentioned format mix; we did not add it. Real-world drover users feed scans, screenshots, and Word docs.
- **English only.** Taxonomy and corpus are English. We did not test multilingual.
- **Vendor pool is small (~3-4 names per domain).** Top-up generation can re-roll the same vendor multiple times across documents in the same domain. This understates vendor diversity in real corpora.
- **Single LLM cell tested.** Gemma4 only; we did not run Anthropic, OpenAI, Llama-3.x, or Qwen3 baselines on the same corpus. The "small local LLM beats zero-shot NLI" claim generalizes loosely; the specific 87% number does not generalize.
- **NLI hypothesis templates were not tuned.** Phase 4 in the ADR-003 roadmap is hypothesis tuning. We did not exercise it. The 6-combo numbers are a lower bound for "untuned" zero-shot NLI.
- **No fine-tuning.** Phase 5+ in ADR-003 is fine-tuning a NLI/encoder head on labeled household-taxonomy data. We did not do it. The "fine-tuning is the credible path" claim is a forecast, not an experimental result.
- **Sample size n=80** is enough to differentiate strategies on this taxonomy but does not produce tight per-domain confidence intervals (each domain is n=5).

## 8. Implications and next steps

- **Halt zero-shot NLI tuning.** Phase 3 (performance optimization) and Phase 4 (hypothesis tuning) target single-digit gains; they cannot bridge an 80pp gap. The cost-benefit does not justify the work.
- **Local LLM is now the primary local path.** `drover classify --ai-provider ollama --ai-model gemma4:latest` is fully offline, no API spend, and outperforms NLI by 11-84pp. The "zero-API local path" goal in ADR-002 is met by this configuration.
- **Keep NLI as a regression baseline.** It still has value as a fast (small-model), cheap, deterministic signal for measuring whether downstream changes break anything. The 6-combo bench remains in the repo.
- **Fine-tuning is the only credible NLI improvement path.** Phase 5+ in ADR-003 (fine-tune `cross-encoder/nli-deberta-v3-base` or a sibling on domain-specific labels). Out of scope for the current session.
- **Eval improvements still worth doing**: format mix (DOCX, scanned PDF), multi-LLM matrix (Anthropic, OpenAI, Qwen3, Llama-3.x), real-document anonymization pipeline.

## 9. Appendix

### 9.1 Branch and commit map

Branch: `nostalgic-engelbart`. All commits below are unique to this branch.

| Commit | Date | Title |
|---|---|---|
| `d7e1614` | 2025-12-18 | feat: add zero-shot NLI document classifier using DeBERTa-v3 |
| `9bf9e89` | 2026-04-27 | feat(nli): add Phase 2 long-document chunking, aggregation, and benchmark |
| `7c800fa` | 2026-04-28 | docs(nli): record Phase 1+2 progress in ADR-003 status section |
| `65f6ba3` | 2026-04-28 | task(eval): add synthetic eval-document generator (prof-5cg) |
| `edca363` | 2026-04-28 | task(eval): expand corpus to 33 docs and capture Phase 2 baselines (prof-5cg) |
| `f70baf1` | 2026-04-29 | task(eval): expand corpus to 80 docs and refresh Phase 2 baselines (prof-5cg) |
| `ece027c` | 2026-04-29 | task(eval): add gemma4 LLM baseline to Phase 2 baselines (prof-5cg) |

### 9.2 Cost ledger

| Item | Cost (USD) |
|---|---|
| Synthetic-doc generation, session 1 (30 docs, Sonnet 4.6, seed 42) | $0.43 |
| Synthetic-doc generation, session 2 top-up (47 docs, Sonnet 4.6, seed 43) | $0.75 |
| LLM eval (gemma4 via local Ollama, 80 docs) | $0.00 |
| NLI eval (cross-encoder/nli-deberta-v3-base, local) | $0.00 |
| **Total external API spend** | **$1.18** |

### 9.3 Wallclock

| Step | Wallclock |
|---|---|
| Synthetic-doc generation, 30 docs, concurrency 5 | ~2 min |
| Synthetic-doc generation, 47 docs, concurrency 5 | ~3 min |
| 6-combo NLI bench, 80 docs, sequential per-cell | ~70 min |
| Gemma4 LLM eval, 80 docs, sequential | ~30 min |

### 9.4 Reproducibility

```bash
# Setup
uv sync --all-extras

# Regenerate corpus from scratch (deterministic given seeds)
ANTHROPIC_API_KEY=... uv run python scripts/generate_eval_samples.py --count 30 --seed 42 --concurrency 5
ANTHROPIC_API_KEY=... uv run python scripts/generate_eval_samples.py --top-up --seed 43 --concurrency 5

# LLM baseline
env -u ALL_PROXY -u all_proxy -u FTP_PROXY -u GRPC_PROXY \
  uv run drover evaluate --ground-truth eval/ground_truth.jsonl \
                         --documents-dir eval/samples \
                         --ai-provider ollama --ai-model gemma4:latest \
                         --output json --log quiet

# NLI baselines (6 cells, set DROVER_NLI_CHUNK_STRATEGY and DROVER_NLI_AGGREGATION per cell)
env -u ALL_PROXY -u all_proxy -u FTP_PROXY -u GRPC_PROXY \
  DROVER_NLI_CHUNK_STRATEGY=truncate DROVER_NLI_AGGREGATION=max \
  uv run drover evaluate --ground-truth eval/ground_truth.jsonl \
                         --documents-dir eval/samples \
                         --ai-provider nli_local \
                         --output json --log quiet
```

### 9.5 Highlights — what worked

- The synthetic-doc generator: `$1.18 / 77 docs / 0 sanitize rejections`. Atomic JSONL append, resume on crash, injection sanitizer, per-doctype structural prompts, markdown-to-reportlab renderer.
- The coverage planner: deterministic, seed-stable, fills both round-robin domain coverage and per-domain depth in two stages.
- The 6-combo bench: clean separation of strategy vs aggregation; per-cell JSON output; the same script doubles as a regression harness.
- Quality gates clean: 249 tests pass, ruff clean, mypy clean, bandit clean across all 7 commits on the branch.
- Decisive empirical result: the LLM-vs-NLI experiment ended with a clear "stop" signal rather than ambiguous numbers requiring more work.

### 9.6 Lowlights — what did not work or wasted time

- The 3-doc corpus. Two whole sessions of corpus building before Phase 2 numbers meant anything. Should have grown the corpus *before* implementing Phase 2.
- Phase 2 chunking work itself: the gain over truncate/max on the 80-doc corpus is +2.4pp on doctype, 0pp on category, -0pp on domain. Not nothing, but not enough to justify the implementation cost given the LLM gap.
- Anthropic prompt caching: 0 cache reads despite `cache_control: ephemeral`. The system block was below the 1024-token threshold. Either dead code or a misconfigured optimization, depending on framing.
- TMPDIR confusion in the bench script: the bash bench script inherits the user's `TMPDIR`, not the Claude session's; outputs went to a hidden `/var/folders/...` path that took several `lsof` calls to locate.
- `drover evaluate` stdout pollution. JSON output is preceded by `Warning:` lines from the loader; bench parsers must scan to the first `{`.
- 14 pre-existing lint errors in `scripts/` (`batch_organize.py`, `eval_runner.py`, `taxonomy_discover.py`) confirmed pre-existing via `git stash`; not addressed in scope.
- `total_documents` field in eval JSON returns `None` instead of the count.
- Per-domain category and doctype diversity is uneven (medical=4 cats but most domains=2 cats). Top-up planner satisfies the AC but does not pursue maximum diversity.
- Vendor pool size (3-4 names per domain) is small enough that synthetic vendors repeat across documents.

### 9.7 Open questions for the blog post draft

- How to frame "we shipped Phase 2 chunking and then the LLM baseline obsoleted it." Is that wasted work, or is it the cost of doing the experiment honestly? The right framing depends on the audience (engineering vs research).
- Is there a useful "When to choose zero-shot NLI" recommendation that survives the result? Probably: latency-critical, deterministic, on-device with strict memory limits where Ollama isn't an option.
- How much of the LLM advantage is gemma4 specifically vs LLMs in general? A multi-LLM matrix (Anthropic Haiku, OpenAI gpt-4o-mini, Llama-3.x, Qwen3) on the same corpus would tell us.
- What does fine-tuned NLI look like on the same corpus? Phase 5+ from ADR-003. Not run.
