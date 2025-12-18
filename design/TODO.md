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

## Encoder Classifier Implementation

- [ ] Discuss implementing a zero-shot NLI encoder classifier using cross-encoder/nli-deberta-v3-base that classifies documents by scoring natural language hypotheses against document text using entailment, as an alternative to the current generative LLM approach.

- [ ] Explore how to craft effective natural language hypothesis mappings for each of the 19 taxonomy domains that describe what documents in that domain look like, since hypothesis quality directly impacts NLI classification accuracy.

- [ ] Discuss implementing hierarchical category classification where the encoder first predicts domain, then classifies into categories valid only within that predicted domain, returning ranked results with confidence scores.

- [ ] Explore how to build doctype hypotheses for the ~50 canonical document types that distinguish between similar types like "statement" versus "invoice" versus "receipt" effectively.

- [ ] Discuss confidence calibration approaches using softmax normalization over entailment logits to produce probability distributions, and how to set appropriate thresholds for fallback to full LLM classification.

---

## Hybrid Pipeline Integration

- [ ] Design a hybrid classifier that uses the encoder for domain/category/doctype classification and delegates only vendor/date/subject extraction to the LLM, exploring how to handle low-confidence encoder predictions.

- [ ] Discuss creating a simplified extraction-only prompt that accepts pre-classified fields and extracts only vendor, date, and subject, estimating the token savings versus the full classification prompt.

- [ ] Explore adding a classifier mode option that lets users choose between full LLM classification, encoder-only, or hybrid approaches depending on their accuracy/speed tradeoffs.

- [ ] Discuss what configuration options the encoder classifier needs and how to integrate them with Drover's existing YAML config and CLI patterns.

---

## Confidence Scoring and Routing

- [ ] Explore adding confidence scores to classification output and discuss how to extract meaningful confidence from both encoder predictions (softmax) and LLM responses (token log-probabilities).

- [ ] Discuss implementing confidence-based routing that surfaces uncertain classifications for human review, since the current taxonomy fallback mode masks uncertainty by silently mapping unknown values to "other".

- [ ] Design a human review workflow that filters batch classification results to show only low-confidence or error cases in a format optimized for quick manual correction.

- [ ] Explore confidence calibration metrics like Expected Calibration Error that measure whether predicted confidence correlates with actual accuracy, and how to surface this in evaluation reports.

---

## Model and Evaluation Improvements

- [ ] Discuss switching the default Ollama model from Llama 3.2 to Qwen 2.5, comparing their structured output capabilities and document understanding performance.

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

- [ ] Discuss batch inference approaches for the encoder classifier that process multiple documents in a single forward pass for improved throughput on large document sets.

- [ ] Explore parallel processing strategies that run document loading concurrently with classification to hide I/O latency when processing batches.

- [ ] Design a benchmarking methodology that measures latency, throughput, token consumption, and memory usage across different model configurations for informed model selection.
