# ADR-005: Docling with Full-Page OCR as the Default PDF Loader

## Status

Accepted (2026-05-01).

## Context

`drover classify` outputs a suggested filesystem path of the form `{domain}/{category}/{doctype}/{filename}`. The leading three segments determine where the file lands; the filename carries vendor, date, and subject. The loader is the first pipeline stage and produces the text the LLM classifies on top of.

PDFs in the target workload (household paperwork: receipts, invoices, policies, statements, scanned forms) regularly carry vendor identity in logos, page-corner imagery, and embedded graphics. A loader that flattens to text-layer content alone cannot see that information.

Two viable PDF loaders exist:

- **`unstructured`**: text-layer extraction via `unstructured.partition.auto`. Fast, no external models, born-digital text only.
- **[Docling](https://docling-project.github.io/docling/)**: structure-aware parser with optional OCR enrichment. Produces a `DoclingDocument` carrying section hierarchy, tables, and pictures; can run OCR over the full page so logo and image text reaches the prompt.

## Decision

Use Docling as the default loader, with full-page OCR enabled. Fall back to `unstructured` via `--loader unstructured` or `DROVER_LOADER=unstructured`.

Concretely (`src/drover/loader.py:_build_docling_converter`):

```python
PdfPipelineOptions(
    do_ocr=True,
    ocr_options.force_full_page_ocr=True,
    ocr_options.bitmap_area_threshold=0.0,
)
```

The classifier consumes `docling_doc.export_to_markdown()` as the prompt input.

## Rationale

The user-facing metric is path correctness: did `drover` put the file in the right folder? Path correctness requires `domain`, `category`, and `doctype` all to match.

On the 14-document real-world corpus at `eval/samples/real-world/` (gemma4:latest via Ollama, n=11 successfully classified by both loaders):

| Axis | Docling + full-page OCR | unstructured |
|---|---|---|
| domain | 0.545 | 0.636 |
| category | 0.455 | 0.273 |
| doctype | 0.727 | 0.545 |
| vendor | 0.182 | 0.364 |
| date | 0.364 | 0.636 |
| **path joint (domain ∩ category ∩ doctype)** | **0.455** | **0.182** |
| filename joint (vendor ∩ date) | 0.091 | 0.273 |

Docling roughly doubles path-joint accuracy. The structural cues full-page OCR produces (section headers in the markdown export, OCR'd text from logos and embedded images) help the classifier disambiguate categories that flat text leaves ambiguous.

The filename joint regresses. OCR re-transcribes clean text-layer content with noise: words concatenate ("Mouser Electronics" becomes "MouserElectronics"), trademark glyphs (`®`) appear and break fuzzy match, and dates spanning bitmap regions occasionally emit "00000000". This is a real cost.

Path correctness wins the trade-off. A misclassified file lands in a wrong folder where the user is unlikely to find it again. A slightly-off filename lands in the right folder and is repairable by rename. Drover exists to organize files into folders; the path is the load-bearing output.

## Consequences

- Folder placement improves materially over the `unstructured` baseline.
- Filename quality regresses on vendor and date. Repair via manual rename or downstream extraction step.
- Per-document loader latency rises from ~60 ms to ~3.7 seconds. The LLM call still dominates total wallclock.
- First-time install requires the `[docling]` extra and a one-time model download: `uv sync --extra docling` followed by `uv run docling-tools models download` (~500 MB to `~/.cache/docling/models`). Subsequent runs are offline.
- Long Docling markdown (~30K+ chars) can trigger gemma4 into emitting tool-call output instead of structured JSON, producing `LLM_PARSE_ERROR` and skipping the document. Affects 3 of 14 docs in the eval corpus. A page-sampling or markdown-truncation step before the prompt would mitigate; out of scope for this ADR.

## References

- Corpus: `eval/samples/real-world/` (14 PDFs, local only; ground truth at `eval/ground_truth/real-world.jsonl`).
- Run artifacts: `eval/runs/real-world-2026-04-30T184932/` (full-page OCR), with per-doc JSON outputs and `results.md`.
- Implementation: `src/drover/loader.py`, `src/drover/classifier.py`, `src/drover/config.py`.
- Beads: `prof-m78`.
