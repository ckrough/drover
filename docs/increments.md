# Long-Term Implementation Plan

## Purpose

This document is Drover's **living roadmap**. It breaks future work into small, shippable increments so we always know what's next and never lose track of good ideas.

**Why increments?** Large projects fail when they try to do everything at once. Increments let us:
- Ship value early and often
- Learn from real usage before building more
- Change direction without wasting work

---

## Rules for Productive Development

### Agile Principles

1. **Working software over comprehensive plans** — Ship something small that works, then iterate
2. **Respond to change over following a plan** — This roadmap will evolve; that's expected
3. **Deliver frequently** — Aim for increments that take days/weeks, not months
4. **Simplicity** — Maximize work not done; build only what's needed now

### Increment Rules

1. **Each stage must be independently deployable** — No half-finished features
2. **Complete one stage before starting the next** — Avoid work-in-progress pile-up
3. **Smallest viable scope** — If an item can be split, split it
4. **Definition of done** — Tests pass, docs updated, code reviewed

### Prioritization

1. **Fix bugs before adding features** — Broken software erodes trust
2. **Infrastructure before features** — CI/testing unlocks safe iteration
3. **User pain over developer convenience** — Solve real problems first
4. **Say no by default** — Every feature has ongoing maintenance cost

---

## Roadmap

The following stages outline planned enhancements, organized so each builds on previous work and delivers independently valuable functionality.

---

## Stage 1: Developer Experience & CI Foundation

Establish automated quality gates and consistent development workflows.

### Pre-commit Hooks
- [ ] Add pre-commit framework with ruff, mypy, and bandit hooks
- [ ] Configure commit message linting (conventional commits)
- [ ] Add NLTK data check to prevent missing dependency errors
- [ ] Document hook installation in CONTRIBUTING.md

### GitHub Actions CI Pipeline
- [ ] Create workflow for lint, type-check, and test on PR
- [ ] Add matrix testing across OS platforms (Ubuntu, macOS, Windows) with Python 3.13
- [ ] Configure dependency caching for faster builds
- [ ] Add security scanning (pip-audit, bandit)
- [ ] Set up coverage reporting with threshold enforcement

---

## Stage 2: Prompt Engineering & Reproducibility

Enable systematic prompt iteration and A/B testing.

### Prompt Versioning
- [ ] Implement prompt template registry with version identifiers
- [ ] Add prompt hash to classification metrics for traceability
- [ ] Create prompt changelog format for tracking changes
- [ ] Support loading specific prompt versions via config
- [ ] Add CLI flag `--prompt-version` for reproducible runs

---

## Stage 3: Enhanced Evaluation & Error Analysis

Improve understanding of classification performance and failure modes.

### Confusion Matrix Visualization
- [ ] Generate confusion matrices from evaluation results
- [ ] Add ASCII/terminal visualization for CLI output
- [ ] Export to HTML/PNG for reports
- [ ] Calculate per-class precision, recall, F1 scores
- [ ] Highlight systematic misclassification patterns

### Evaluation Enhancements
- [ ] Add stratified sampling for balanced test sets
- [ ] Support cross-validation for small datasets
- [ ] Track evaluation metrics over time (trend analysis)

---

## Stage 4: Classification Quality & Active Learning

Enable continuous model improvement through feedback loops.

### Confidence Scores
- [ ] Extract token probabilities from LLM responses where available
- [ ] Implement calibrated confidence scoring heuristics
- [ ] Add `confidence` field to ClassificationResult
- [ ] Support `--min-confidence` threshold for automatic vs. manual review
- [ ] Flag low-confidence results for human review

### Active Learning Pipeline
- [ ] Queue low-confidence samples for annotation
- [ ] Track human corrections for retraining signals
- [ ] Generate training data export for fine-tuning
- [ ] Measure confidence calibration accuracy

---

## Stage 5: Production Observability

Enable debugging and monitoring in production deployments.

### OpenTelemetry Tracing
- [ ] Add OpenTelemetry SDK integration
- [ ] Instrument LLM calls with span attributes (model, tokens, latency)
- [ ] Trace document loading and parsing stages
- [ ] Add trace context to classification results
- [ ] Support OTLP export to Jaeger/Zipkin/Grafana Tempo
- [ ] Document tracing setup for self-hosted deployments

### Metrics & Monitoring
- [ ] Export Prometheus metrics for classification throughput
- [ ] Track error rates by document type and provider
- [ ] Add health check endpoint for service deployments

---

## Stage 6: Advanced Features

Future enhancements beyond core functionality.

### Performance Optimization
- [ ] Implement result caching with content hashing
- [ ] Add batch API support for providers that offer it
- [ ] Async document loading for parallel I/O

### User Experience
- [ ] Interactive mode for manual classification review
- [ ] Watch mode for automatic folder processing
- [ ] Integration with cloud storage (S3, GCS)

---

## Prioritization Notes

| Item | Impact | Effort | Dependencies |
|------|--------|--------|--------------|
| Pre-commit hooks | High | Low | None |
| GitHub Actions CI | High | Medium | None |
| Prompt versioning | Medium | Medium | None |
| Confusion matrix | Medium | Low | Evaluation framework |
| Confidence scores | High | Medium | Provider-specific logic |
| OpenTelemetry | Medium | Medium | None |

---

## Contributing

To propose changes to this roadmap, open an issue or discuss in a PR. Priorities may shift based on user feedback and project needs.
