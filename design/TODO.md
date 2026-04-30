# Drover Development TODO

Discussion prompts for improving document classification accuracy and throughput. Each task is a conversation starter for exploring approaches with AI coding assistance.

## Context

Drover currently uses a single generative LLM (via LangChain) to classify documents into a hierarchical taxonomy and extract metadata fields. The classifier extracts six fields: domain (19 classes), category (varies by domain), doctype (~50 classes), vendor (open vocabulary), date (YYYYMMDD format), and subject (brief description).

---

## Research and Exploration

- [ ] Discuss the tradeoffs of converting PDFs to rendered per-page PNGs and passing them through a vision-enabled model like Qwen2.5-VL versus the current text extraction pipeline, considering that VLMs can outperform text extraction for scanned documents but add complexity around page segmentation and token costs.

- [ ] Investigate cline-bench as a potential framework for evaluating Drover's classification performance and examine whether its benchmarking patterns could improve our eval infrastructure.

---

## Development Infrastructure

- [ ] Design a devcontainer configuration that provides a consistent development environment with all dependencies pre-installed, enabling contributors to start immediately without manual setup.

- [ ] Explore how to extract Drover's document classification and evaluation workflows into reusable Claude skills with supporting scripts that could apply to similar projects.

---

## Confidence Scoring and Routing

- [ ] Explore adding confidence scores to classification output and discuss how to extract meaningful confidence from LLM responses (token log-probabilities).

- [ ] Discuss implementing confidence-based routing that surfaces uncertain classifications for human review, since the current taxonomy fallback mode masks uncertainty by silently mapping unknown values to "other".

- [ ] Design a human review workflow that filters batch classification results to show only low-confidence or error cases in a format optimized for quick manual correction.

- [ ] Explore confidence calibration metrics like Expected Calibration Error that measure whether predicted confidence correlates with actual accuracy, and how to surface this in evaluation reports.

---

## Model and Evaluation Improvements

- [ ] Explore adding vision model support that renders PDF pages to images and classifies them directly, bypassing text extraction errors for scanned documents.

- [ ] Discuss building a comprehensive ground truth dataset of 50-100 documents covering all 19 domains, prioritizing edge cases like poor scans, handwritten text, multi-page documents, and ambiguous classifications.

- [ ] Explore adding per-field accuracy metrics to evaluation that show separate precision/recall/F1 for each field, with appropriate matching tolerances for vendor names, dates, and subjects.

- [ ] Discuss hierarchical F1 scoring that awards partial credit for near-miss classifications where the domain is correct but category is wrong, distinguishing "completely wrong" from "reasonable guess" errors.

---

## Extraction Optimization

- [ ] Explore regex-based date extraction as a preprocessing step that identifies candidate dates in document text before LLM extraction, potentially reducing date hallucination.

- [ ] Discuss vendor name normalization strategies including alias matching, suffix removal, and formatting standardization to improve consistency across extractions.

- [ ] Explore subject field validation that ensures extracted subjects comply with NARA filename length constraints without requiring LLM re-prompting.

---

## Performance and Throughput

- [ ] Explore parallel processing strategies that run document loading concurrently with classification to hide I/O latency when processing batches.

- [ ] Design a benchmarking methodology that measures latency, throughput, token consumption, and memory usage across different model configurations for informed model selection.
