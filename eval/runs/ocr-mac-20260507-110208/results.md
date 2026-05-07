# OCR backend: ocrmac (Apple Vision)

| Field | Value |
|---|---|
| Date | 2026-05-07 |
| Corpus | synthetic (80 docs) |
| Provider / model | ollama / gemma4:latest |
| Loader | docling |
| OCR backend | ocrmac (Apple Vision via the `ocr-mac` extra) |
| Wall clock | 20 min 23 s |

## Accuracy

| Metric | Result |
|---|---|
| Domain | 81.2% |
| Category | 56.2% |
| Doctype | 96.2% |
| Vendor | 90.0% |
| Date | 90.0% |
| Errors | 0 |

## Deltas vs baseline

Baseline run: `eval/runs/ocr-baseline-rapidocr-20260507-100620/results.md` (rapidocr on torch CPU, same corpus + model).

| Metric | Baseline | ocrmac | Delta |
|---|---|---|---|
| Domain | 80.0% | 81.2% | +1.2 pp |
| Category | 57.5% | 56.2% | -1.3 pp |
| Doctype | 93.8% | 96.2% | +2.4 pp |
| Vendor | 85.0% | 90.0% | +5.0 pp |
| Date | 85.0% | 90.0% | +5.0 pp |
| Wall clock | 3309 s | 1223 s | -2086 s (2.7x faster) |

Doctype, vendor, and date all improve materially; domain ticks up by one document; category drops by one document (within run-to-run noise on this corpus). The wall-clock speedup is the headline win: on this 80-doc synthetic corpus, ocrmac on Apple Vision is roughly 2.7x faster than rapidocr on torch CPU.
