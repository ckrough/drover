# ADR-004: Local LLM via Ollama as the Primary Local Classification Path

## Status
Accepted (2026-04-29). Supersedes ADR-003 (NLI Classifier Roadmap) for Phases 3-8; the Phase 1 and Phase 2 NLI implementations on branch `nostalgic-engelbart` are kept in tree as a regression baseline but no further investment is planned.

**Amended (2026-04-30):** the NLI implementation referenced above as "kept in tree as a regression baseline" has been fully removed on branch `nostalgic-engelbart`. The decision in this ADR is unchanged. The deprecation window described in step 2 of "Decision" is collapsed: there is no `--i-know-this-is-deprecated` shim. `src/drover/nli_classifier.py`, `chunking.py`, `aggregation.py`, the `extractors/` package, and the `[nli]` install extra are gone. The "subject to confirmation in the implementation issue" hedge in step 1 of "Decision" is resolved: `AIConfig.model` default is now `gemma4:latest` in `src/drover/config.py`. See the cleanup commits on `nostalgic-engelbart` for the deletion (refs beads `prof-wis`).

## Context

ADR-002 commits drover to a privacy-first, local-first architecture: documents must not leave the user's machine unless the user explicitly opts into a hosted provider. ADR-003 added a zero-shot NLI classifier (`cross-encoder/nli-deberta-v3-base`) as the first concrete fully-local path: 184M params, no model server, no API cost, hierarchical decoding (domain → category → doctype), with `[nli]` as an optional install extra.

When ADR-003 was written (2025-12-18), the Ollama ecosystem skewed toward larger generative models (Llama-3.1, Llama-3.2, Qwen2-7B+) that were either too slow on consumer hardware or too generative for a classification problem. Zero-shot NLI was the right call at that time because it was the only fully-local path with classifier-grade latency and footprint.

Two things changed by 2026-04:

1. **Local LLM model quality.** Models like `gemma4:latest` (9.6GB, Q4-quantized) now run on M-series Macs with acceptable wallclock for batch classification (~22 seconds per document with structured output). They handle structured-output schemas (`with_structured_output()` in LangChain) reliably enough to produce `RawClassification` JSON in a single call.
2. **Empirical baselines on a balanced 80-document corpus** showed that zero-shot NLI lags a small local LLM by 11-84 percentage points on every classification axis. The full data is in `docs/research/nli-vs-llm-notes.md` and `eval/baselines.md`.

### Empirical result

On the balanced 80-doc eval corpus (5+ docs / 2+ categories / 2+ doctypes per domain across all 16 canonical household-taxonomy domains, 41 docs >512 cross-encoder tokens):

| Metric   | NLI best (any of 6 cells) | gemma4:latest via Ollama | Gap     |
|----------|---------------------------|--------------------------|---------|
| Domain   | 3.8% (truncate / max)     | 87.5%                    | +83.7pp |
| Category | 2.5% (all 6 cells)        | 40.0%                    | +37.5pp |
| Doctype  | 6.2% (sliding / mean+wt)  | 86.2%                    | +80.0pp |
| Vendor   | 1.2% (all 6 cells)        | 78.8%                    | +77.6pp |
| Date     | 77.5% (all 6 cells)       | 88.8%                    | +11.3pp |

The 6-cell NLI matrix exhausts the chunking and aggregation strategies in ADR-003 Phase 2 (`{truncate, sliding, importance} × {max, mean, weighted}`). Phase 3 (performance optimization) and Phase 4 (hypothesis tuning) target single-digit gains; they cannot bridge an 80pp gap. Phase 5 (fine-tuning) could in principle close the gap, but requires a labeled training corpus we do not have and would still constrain future taxonomy changes to a fine-tune cycle.

The local LLM path also extracts vendor and date directly (78.8% and 88.8%) rather than relying on the regex extractor used by NLI (1.2% and 77.5%). This is structural: the LLM reads the surrounding text; the NLI head sees only the entailment task and delegates to a separate `extractors/regex.py` module.

### Why this changes the calculus

- **The "no model server" argument for NLI is weaker than expected.** Ollama is a stable, single-binary install on macOS, Linux, and Windows. The operational difference between "load a HuggingFace cross-encoder via `transformers`" and "talk to a local Ollama daemon" is small for users who already have either toolchain.
- **Per-document cost is now bounded.** Local Ollama inference is bound by user hardware, not API quotas. There is no $/request meter; there is only wallclock.
- **Maintenance cost of two paths is real.** Two classifiers means two prompt formats, two test suites, two sets of hypothesis/extractor tunings, and two failure modes to debug when a user reports a misclassification.

## Decision

1. **Standardize on Ollama (local LLM) as the primary local classification path** for drover. The default `--ai-provider` becomes `ollama`. The default model becomes `gemma4:latest` (subject to confirmation in the implementation issue).
2. **Mark the NLI path deprecated** and remove it from the supported provider list in the next release. Keep the code in-tree for one release as an opt-in escape hatch behind a `--ai-provider nli_local --i-know-this-is-deprecated` flag (or equivalent), then delete.
3. **Keep the 80-doc eval corpus, the synthetic-doc generator, and the 6-cell bench script.** They retain value as a regression harness against any classifier path. The corpus is not NLI-specific.
4. **Supersede ADR-003 Phases 3-8.** Phase 1 (MVP) and Phase 2 (long-document chunking) are kept as historical record; Phases 3-8 are abandoned. Update ADR-003 status to "Superseded by ADR-004."
5. **Hosted providers (`anthropic`, `openai`, `openrouter`) remain supported** as opt-in for users who prefer hosted inference or who run drover on hardware that cannot host a 9.6GB model. Privacy-first defaults stay local; the user explicitly chooses to leave the machine.

## Consequences

### Positive

- **One classification code path to maintain.** `DocumentClassifier` (LangChain `with_structured_output()`) handles all providers (Ollama, Anthropic, OpenAI, OpenRouter). No `NLIDocumentClassifier`, no separate hypothesis-template registry, no separate extractor stack.
- **Materially better accuracy out of the box.** A new user installing drover and pointing it at their documents gets 87.5% domain / 86.2% doctype with no tuning, no extra extras (`uv sync` instead of `uv sync --all-extras`).
- **Vendor and date extraction become first-class.** No more 1.2% vendor accuracy.
- **Smaller install footprint.** Drop `[nli]` extra dependencies: `transformers`, `cross-encoder` model weights (~700MB), `scikit-learn` (Phase 2 importance chunker).
- **No more dual-test burden.** ~37 NLI-specific tests and the `tests/test_aggregation.py` / `tests/test_chunking.py` files become removable.

### Negative

- **Ollama becomes a hard dependency for the local path.** Users who cannot or will not install Ollama must use a hosted provider. NLI offered a pure-Python local fallback; that goes away.
- **Per-document wallclock increases.** Gemma4 with structured output runs ~22s/doc on M-series Mac sequential. NLI on the same hardware ran ~5-12 minutes for the full 80-doc bench (sub-second per doc). The LLM is faster end-to-end but slower per call.
- **Memory footprint at inference time is larger.** Gemma4 needs ~10GB resident; the NLI cross-encoder needs ~700MB. Users with 8GB machines lose the local path.
- **The Phase 2 chunking work is sunk cost.** `src/drover/chunking.py`, `src/drover/aggregation.py`, and the `chunk_strategy` / `aggregation` config knobs become dead code after the NLI path is removed.
- **The branch `nostalgic-engelbart` carries unmerged work that we are partially undoing.** The corpus expansion (commits `65f6ba3`, `edca363`, `f70baf1`) is keep; the Phase 2 NLI implementation (commit `9bf9e89`) is delete. We will land both before opening the cleanup PR so the history reflects the experimental path.

### Neutral

- **Hosted providers continue to work unchanged.** This is not a deprecation of the cloud path; it is a consolidation of the local path.
- **The 6-cell NLI bench script is preserved as a research artifact.** It does not run in CI but remains usable to verify the historical baseline.

## References

- ADR-002: Privacy-First Design
- ADR-003: NLI Classifier Roadmap (superseded for Phases 3-8 by this ADR)
- `docs/research/nli-vs-llm-notes.md`: full research notes including methods, results, lessons learned, limitations
- `eval/baselines.md`: numerical baselines for the 80-doc corpus (LLM and NLI)
- `eval/ground_truth.jsonl`: ground truth for the 80-doc corpus
- `scripts/generate_eval_samples.py`: synthetic-doc generator (preserved)
- Branch `nostalgic-engelbart` commits: `d7e1614` (Phase 1), `9bf9e89` (Phase 2), `65f6ba3` (generator), `edca363` (33-doc), `f70baf1` (80-doc), `ece027c` (LLM baseline), `e735ab9` (research notes)
