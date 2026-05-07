# OCR backend baseline: rapidocr on torch CPU

| Field | Value |
|---|---|
| Date | 2026-05-07 |
| Corpus | synthetic (80 docs) |
| Provider / model | ollama / gemma4:latest |
| Loader | docling |
| OCR backend | rapidocr (torch CPU; ocr-mac extra not installed) |
| Wall clock | 55 min 9 s |

## Accuracy

| Metric | Result |
|---|---|
| Domain | 80.0% |
| Category | 57.5% |
| Doctype | 93.8% |
| Vendor | 85.0% |
| Date | 85.0% |
| Errors | 0 |

## Notes

This is the baseline snapshot captured before the `ocr-mac` extra was added in `prof-91a` / PR #26. With only the `docling` extra installed, Docling's auto-selector falls back to `rapidocr` on the torch CPU backend (`ocrmac`, `easyocr`, and `onnxruntime`-backed `rapidocr` all emit "cannot be used because X is not installed" warnings on startup). Compare against `eval/runs/ocr-mac-20260507-110208/results.md` for the deltas.
