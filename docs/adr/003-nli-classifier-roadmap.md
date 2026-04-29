# ADR-003: NLI Classifier Roadmap

## Status
**Superseded by ADR-004 (2026-04-29)** for Phases 3-8.

Phase 1 (MVP) and Phase 2 (long document handling) implemented on branch `nostalgic-engelbart`; Phases 3-8 abandoned after empirical baselines on the 80-doc corpus showed zero-shot NLI lags a small local LLM (`gemma4:latest`) by 11-84 percentage points on every classification axis. See `docs/adr/004-local-llm-as-primary-local-path.md` and `docs/research/nli-vs-llm-notes.md`.

The Phase 1 and Phase 2 code is retained in-tree as a regression baseline pending removal per the ADR-004 deprecation plan. The text below preserves the original roadmap as historical record.

### Phase Progress

| Phase | Title | State | Branch / Commit |
|-------|-------|-------|-----------------|
| 1 | MVP | **Implemented** | `nostalgic-engelbart` @ `d7e1614` |
| 2 | Long Document Handling | **Implemented** | `nostalgic-engelbart` @ `9bf9e89` |
| 3 | Performance Optimization | Planned | — |
| 4 | Hypothesis Optimization | Planned | — |
| 5 | Advanced Extraction | Planned | — |
| 6 | Confidence and Fallback | Planned | — |
| 7 | Fine-Tuning Pipeline | Planned | — |
| 8 | Integration Improvements | Planned | — |

The branch above adds `chunk_strategy`, `chunk_size`, `chunk_overlap`, `aggregation` to `NLIConfig`; new modules `src/drover/aggregation.py` and `src/drover/chunking.py`; `scikit-learn>=1.3` to the `[nli]` extra; and the Phase 2 Baselines section below. Beads tracker holds the epic `prof-ape` with five child tasks `prof-2oe`, `prof-mnb`, `prof-4xe`, `prof-avq`, `prof-qde`. Per project convention `closed = merged`, those issues stay open until the branch lands on `main`.

Phases 3-8 are documented below as design intent, not commitments; nothing is implemented for them.

## Context
The cloud LLM classifier path (`classifier.py`) requires API access for non-Ollama providers and incurs per-request cost and latency. ADR-002 commits to a privacy-first, local-first architecture. Even Ollama, while local, requires running a separate model server and pulls in generative-LLM tooling for what is fundamentally a classification problem.

A purely local, batteries-included classification path was needed that:

1. Runs offline with no model server dependency.
2. Uses a model sized for classification (hundreds of MB), not generation (multi-GB).
3. Adapts to new taxonomies without retraining (zero-shot).
4. Preserves the existing classifier interface so it slots into `ClassificationService` behind the same factory.

## Decision
Add a second classifier path based on **Natural Language Inference (NLI)** using a cross-encoder model. The classifier scores entailment between document text (premise) and label hypotheses, returning the highest-scoring label per level. Hierarchical decoding (domain → category → doctype) keeps the per-level label set small, which keeps inference fast.

### Phase 1: MVP (delivered, `d7e1614`)

- Zero-shot classification using `cross-encoder/nli-deberta-v3-base`.
- Hierarchical classification: domain → category (conditioned on domain) → doctype (conditioned on category).
- Simple truncation for documents exceeding the 512-token model limit.
- Regex extraction for vendor / date / subject, with optional LLM fallback (`HybridExtractor`).
- New `AIProvider.NLI_LOCAL` and `NLIConfig`; selected via factory in `ClassificationService`.
- Async interface matching the existing `DocumentClassifier`.
- Lazy model loading (downloads on first use).
- Optional dependencies via the `[nli]` extra (`uv sync --extra nli` or `--all-extras`).

### Phase 2: Long Document Handling (delivered, `9bf9e89`)

- `ChunkStrategy` enum (`truncate`, `sliding`, `importance`) and `Aggregation` enum (`max`, `mean`, `weighted`) on `NLIConfig`, plus `chunk_size` (default 400) and `chunk_overlap` (default 100). Validators reject `chunk_overlap >= chunk_size` and `chunk_size > 510`.
- Env-var passthrough: `DROVER_NLI_CHUNK_STRATEGY` / `CHUNK_SIZE` / `CHUNK_OVERLAP` / `AGGREGATION`.
- `src/drover/aggregation.py` with `aggregate_max`, `aggregate_mean`, `aggregate_weighted` (endpoints 2x, middle 1x), and an `AGGREGATORS` registry.
- `src/drover/chunking.py` with `chunk_truncate`, `chunk_sliding` (overlapping windows covering the full document), and `chunk_importance` (TF-IDF-scored sentences via `scikit-learn`, lazy-imported), and a `CHUNKERS` registry.
- `NLIDocumentClassifier._classify_level` chunks the content, scores each `(chunk, hypothesis)` pair, max-pools across hypothesis templates per chunk, and aggregates per label using `AGGREGATORS[self.aggregation]`. Debug payload exposes `chunk_strategy`, `aggregation`, `chunk_count`, per-level `chunk_counts`, and per-level per-chunk per-label `chunk_scores`.
- `scikit-learn>=1.3,<2.0` added to the `[nli]` extra plus a mypy override.
- 37 new tests across `tests/test_aggregation.py` (15), `tests/test_chunking.py` (14), `tests/test_config.py` (8); the existing NLI integration test now patches `_get_chunks` instead of `_truncate_content`.

Defaults preserve Phase 1 behavior: `chunk_strategy=truncate` and `aggregation=max` give the original single-chunk-per-document score path.

## Phase 2: Long Document Handling

### Chunking Strategies

**Sliding Window Chunking**
```python
def chunk_with_overlap(content: str, chunk_size: int = 400, overlap: int = 100):
    """Split document into overlapping chunks for better context."""
    tokens = tokenizer.encode(content)
    chunks = []
    for i in range(0, len(tokens), chunk_size - overlap):
        chunk = tokens[i:i + chunk_size]
        chunks.append(tokenizer.decode(chunk))
    return chunks
```

**Importance-Based Sampling**
- Use TF-IDF to identify key sentences
- Sample first paragraph, key sentences, and last paragraph
- Preserves document structure while fitting token limit

**Aggregation Strategies**
- Max pooling: Use highest entailment score across chunks
- Mean pooling: Average scores (good for consistent documents)
- Weighted: Weight first/last chunks higher (structure-aware)

### Implementation Tasks
- [ ] Add `chunk_strategy` config option: `truncate`, `sliding`, `importance`
- [ ] Implement chunk aggregation methods
- [ ] Benchmark accuracy vs. truncation approach
- [ ] Add metrics for chunk count and aggregation method

## Phase 3: Performance Optimization

### Batch Processing
```python
async def classify_batch(documents: list[str]) -> list[RawClassification]:
    """Process multiple documents in a single model pass."""
    # Batch all premise-hypothesis pairs
    pairs = []
    for doc in documents:
        for label in labels:
            pairs.append((doc, hypothesis(label)))

    # Single forward pass
    scores = model.predict(pairs, batch_size=32)

    # Reshape and select best labels
    return extract_classifications(scores, documents, labels)
```

### GPU Acceleration
- Add CUDA/MPS detection and optimization
- Implement half-precision (FP16) inference
- Add model quantization (INT8) for CPU deployment

### Model Caching
- Cache model in memory across classifications
- Add model warmup on service start
- Implement model unloading for memory management

### Implementation Tasks
- [ ] Add `batch_size` config option
- [ ] Implement batched inference
- [ ] Add FP16 inference option
- [ ] Implement INT8 quantization option
- [ ] Add model warmup command

## Phase 4: Hypothesis Optimization

### Template A/B Testing Framework
```python
class HypothesisOptimizer:
    """Test and select optimal hypothesis templates."""

    TEMPLATE_VARIANTS = {
        "domain": [
            "This document belongs to the {label} domain.",
            "This is a {label} document.",
            "This document is about {label}.",
            "The main topic is {label}.",
        ],
    }

    def optimize(self, ground_truth: list[tuple[str, str]]) -> dict[str, str]:
        """Find best template for each classification level."""
        results = {}
        for level, templates in self.TEMPLATE_VARIANTS.items():
            best_template = None
            best_accuracy = 0
            for template in templates:
                accuracy = self.evaluate_template(template, ground_truth)
                if accuracy > best_accuracy:
                    best_template = template
                    best_accuracy = accuracy
            results[level] = best_template
        return results
```

### Taxonomy-Specific Hypotheses
- Generate contextual hypotheses from taxonomy descriptions
- Use category hierarchies in hypothesis generation
- Add domain-specific keywords to hypotheses

### Implementation Tasks
- [ ] Add hypothesis template configuration
- [ ] Create template optimization command
- [ ] Store optimized templates in taxonomy
- [ ] Add per-taxonomy template overrides

## Phase 5: Advanced Extraction

### SpaCy NER Extractor
```python
class SpacyExtractor(BaseExtractor):
    """Extract metadata using SpaCy NER."""

    def __init__(self, model: str = "en_core_web_sm"):
        self.nlp = spacy.load(model)

    def extract(self, content: str) -> ExtractionResult:
        doc = self.nlp(content[:10000])  # Limit for performance

        vendor = self._extract_org(doc)
        date = self._extract_date(doc)
        subject = self._extract_subject(doc)

        return ExtractionResult(vendor, date, subject)
```

### Enhanced Date Extraction
- Use dateutil for flexible parsing
- Handle relative dates ("last month", "Q3 2024")
- Extract date ranges and fiscal periods

### Implementation Tasks
- [ ] Add SpaCy extractor option
- [ ] Implement enhanced date parsing
- [ ] Add vendor name normalization
- [ ] Create extraction accuracy benchmark

## Phase 6: Confidence and Fallback

### Confidence Thresholds
```python
class ConfidenceConfig:
    """Configuration for confidence-based fallback."""

    min_domain_confidence: float = 0.6
    min_category_confidence: float = 0.5
    min_doctype_confidence: float = 0.5
    fallback_to_llm: bool = True
```

### Hybrid Classification
```python
async def classify_with_fallback(content: str) -> RawClassification:
    """Use NLI with LLM fallback for low confidence."""
    result, debug = await nli_classifier.classify(content)

    if debug["domain_scores"][result.domain] < config.min_domain_confidence:
        # Fall back to LLM for this document
        return await llm_classifier.classify(content)

    return result
```

### Implementation Tasks
- [ ] Add confidence threshold configuration
- [ ] Implement LLM fallback for low-confidence results
- [ ] Add confidence scores to output
- [ ] Create confidence calibration tooling

## Phase 7: Fine-Tuning Pipeline

### Data Preparation
```python
def prepare_nli_training_data(
    documents: list[tuple[str, RawClassification]]
) -> Dataset:
    """Convert labeled documents to NLI training format."""
    examples = []
    for doc, label in documents:
        # Positive example (entailment)
        examples.append({
            "premise": doc,
            "hypothesis": f"This document is a {label.domain} document.",
            "label": 2,  # entailment
        })
        # Negative examples (contradiction)
        for other_domain in all_domains - {label.domain}:
            examples.append({
                "premise": doc,
                "hypothesis": f"This document is a {other_domain} document.",
                "label": 0,  # contradiction
            })
    return Dataset.from_list(examples)
```

### Training Script
```bash
# Fine-tune on custom taxonomy
drover nli train \
    --ground-truth eval/ground_truth.jsonl \
    --documents-dir ./documents \
    --output-model ./models/drover-nli-finetuned \
    --epochs 3 \
    --batch-size 8
```

### Implementation Tasks
- [ ] Create `drover nli train` command
- [ ] Implement data preparation pipeline
- [ ] Add training with HuggingFace Trainer
- [ ] Create model export and loading
- [ ] Add fine-tuned model config option

## Phase 8: Integration Improvements

### Streaming Progress
- Add progress callbacks during classification
- Show model loading progress
- Display per-document timing

### CLI Enhancements
```bash
# Use NLI classifier
drover classify document.pdf --ai-provider nli_local

# With custom NLI model
drover classify document.pdf --ai-provider nli_local \
    --nli-model ./models/drover-nli-finetuned

# With confidence threshold
drover classify document.pdf --ai-provider nli_local \
    --min-confidence 0.7 --fallback-to-llm
```

### Implementation Tasks
- [ ] Add `--nli-model` CLI option
- [ ] Add `--min-confidence` CLI option
- [ ] Add `--fallback-to-llm` CLI option
- [ ] Show classification confidence in output

## Benchmarks

### Accuracy Targets
| Dataset | Zero-Shot Target | Fine-Tuned Target |
|---------|-----------------|-------------------|
| Household taxonomy | 75% | 90% |
| Financial docs | 80% | 92% |
| Medical docs | 70% | 88% |

### Performance Targets
| Metric | CPU Target | GPU Target |
|--------|-----------|------------|
| Single doc latency | 200ms | 50ms |
| Batch throughput | 10 docs/sec | 50 docs/sec |
| Model load time | 5s | 3s |

### Phase 2 Baselines (2026-04-27)

Run on `eval/ground_truth.jsonl` against `cross-encoder/nli-deberta-v3-base` on CPU.
Eval set is 3 documents: `medical_bill.pdf` (619 tokens), `receipt.pdf`, `user_manual.pdf`.

| Strategy | Domain | Category | Doctype | Vendor | Date |
|---|---|---|---|---|---|
| `truncate` × `max` (Phase 1 baseline) | 0.0% | 0.0% | 33.3% | 0.0% | 33.3% |
| `sliding` × `max` | 0.0% | 0.0% | 33.3% | 0.0% | 33.3% |
| `sliding` × `mean` | 0.0% | 0.0% | 33.3% | 0.0% | 33.3% |
| `sliding` × `weighted` | 0.0% | 0.0% | 33.3% | 0.0% | 33.3% |
| `importance` × `max` | 0.0% | 0.0% | 33.3% | 0.0% | 33.3% |
| `importance` × `weighted` | 0.0% | 0.0% | 33.3% | 0.0% | 33.3% |

**Read these numbers with extreme skepticism.** All six combinations produce *identical* per-document predictions. Two reasons:

1. **The eval set is too small to differentiate strategies.** `medical_bill.pdf` is the only document that exceeds the 512-token cross-encoder limit (619 tokens). The two sliding windows on a 619-token document are 0-400 and 300-619, which share most of their content; max-pooling across them returns essentially the same score truncate would have produced. `receipt.pdf` and `user_manual.pdf` fit in a single chunk, so chunker selection is a no-op for them.
2. **The corpus does not exercise the failure modes Phase 2 was built to address.** Sliding/importance pay off when the document-type signal lives in middle or trailing pages (statements with itemized line items, contracts with body text after a boilerplate header). On a 3-doc corpus of mostly-short documents, those cases are absent.

The 619-token tokenizer warning fires once per run for every strategy because the chunkers themselves call `tokenizer.encode(content)` to measure document length before splitting. This is benign — only the resulting chunks are fed to the entailment model — but it does mean the user-visible warning isn't a reliable signal that "Phase 2 is doing work." Use the `chunk_count` field in the debug payload instead.

**What changed despite the matched accuracy numbers:**

- The classifier's debug payload now distinguishes `chunk_strategy`, `aggregation`, `chunk_count`, `chunk_counts` (per level), and `chunk_scores` (per level, per chunk, per label). This makes failure analysis tractable.
- All four `chunk_strategy` values are reachable through config / env / CLI, with TF-IDF-driven importance sampling backed by `scikit-learn`.
- `_classify_level` no longer assumes a single-chunk premise; it scores per chunk and aggregates per label.

**Next step:** prof-5cg (grow eval set) is the prerequisite for any meaningful Phase 2 conclusion. Until then, the table above functions as a smoke test, not a benchmark.

## Dependencies

### Required for Fine-Tuning
```toml
[project.optional-dependencies]
nli-train = [
    "transformers[torch]>=4.35,<5.0",
    "datasets>=2.14,<3.0",
    "accelerate>=0.24,<1.0",
    "evaluate>=0.4,<1.0",
]
```

### Optional for SpaCy Extraction
```toml
nli-spacy = [
    "spacy>=3.7,<4.0",
]
```

## Consequences

### Positive
- **Offline by default.** No API key, no model server, no network calls during classification.
- **Reinforces ADR-002.** Adds a stronger local-first path for the most privacy-sensitive deployments.
- **Adapts to new taxonomies without retraining.** Hypotheses are generated from taxonomy labels at runtime.
- **Smaller artifact than generative LLMs.** DeBERTa-v3-base is ~440 MB on disk vs. multi-GB for Ollama models.
- **Composable with the LLM path.** The factory in `ClassificationService` can fall back to the LLM classifier per-document (Phase 6).

### Negative
- **Token-limit ceiling.** The cross-encoder caps at ~512 tokens, so long documents need chunking (Phase 2) to avoid silent truncation bias.
- **Hypothesis sensitivity.** Zero-shot accuracy depends heavily on hypothesis phrasing (Phase 4 addresses this).
- **First-run latency.** Initial model download is ~440 MB; lazy-loaded but still a UX cost on first use.
- **Heavier optional dependency.** `torch` adds significant disk footprint to the `[nli]` extra.
- **Lower out-of-the-box accuracy than tuned LLMs.** Targets in Benchmarks reflect this; fine-tuning (Phase 7) closes the gap.

### Mitigations
- The `[nli]` extra is opt-in; users not invoking `nli_local` never install torch/transformers.
- Confidence-based LLM fallback (Phase 6) preserves accuracy for ambiguous documents while keeping the common case offline.
- Benchmarks are recorded against `eval/ground_truth.jsonl` to track the zero-shot baseline before each phase lands.

## Related
- `src/drover/nli_classifier.py` — `NLIDocumentClassifier`
- `src/drover/extractors/{base,regex,llm}.py` — metadata extractors used by the NLI path
- `src/drover/config.py` — `AIProvider.NLI_LOCAL`, `NLIConfig`, `ExtractorType`
- `src/drover/service.py` — factory selecting between LLM and NLI classifier
- `tests/test_nli_classifier.py` — unit tests for the classifier
- ADR-001: Chain-of-Thought Prompting Strategy (LLM classifier reasoning)
- ADR-002: Privacy-First Design (motivates local-first NLI)
