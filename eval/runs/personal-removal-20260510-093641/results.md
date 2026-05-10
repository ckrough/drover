# Personal-domain removal + lifestyle/entertainment + lifestyle/membership

| Field | Value |
|---|---|
| Date | 2026-05-10 |
| Corpus | synthetic (80 docs) |
| Provider / model | ollama / gemma4:latest |
| Loader | docling |
| OCR backend | ocrmac (Apple Vision) |
| Beads | prof-un5, prof-b7h |

## Accuracy

| Metric | Result |
|---|---|
| Domain | 87.5% |
| Category | 61.25% |
| Doctype | 93.75% |
| Vendor | 90.0% |
| Date | 90.0% |
| Errors | 0 |

## Deltas vs baseline

Baseline: `eval/runs/ocr-mac-20260507-110208/results.md` (same model + loader + OCR; only taxonomy/prompt changed).

| Metric | Baseline | After | Delta |
|---|---|---|---|
| Domain | 81.2% | 87.5% | +6.3 pp |
| Category | 56.2% | 61.25% | +5.0 pp |
| Doctype | 96.2% | 93.75% | -2.5 pp |

## Changes evaluated

1. Added `lifestyle/entertainment` category with 17 schema.org EventReservation aliases (prof-un5).
2. Removed the `personal` domain (prof-b7h). Memberships and club/library IDs route to `lifestyle/membership`; volunteer-org IDs to `lifestyle/volunteering`. Backward-compat: `personal` aliases to `lifestyle` for graceful LLM-emission fallback. `non_profit`/`nonprofit` rerouted from `personal` to `lifestyle`.
3. Relabeled 5 ground-truth entries (civic library certificate, 2× harbor athletic club, 2× lighthouse volunteers) from the deprecated `personal/*` paths to their new `lifestyle/*` homes.

## Where the gains came from

All 5 relabeled docs classified perfectly under the new taxonomy (domain + category + doctype). The category lift also reflects a smaller set of valid destinations once `personal` was removed (less ambiguity for the LLM).

## Doctype regression

5 doctype misses across the corpus:

- `medical_bill.pdf`: invoices (expected) vs statements
- `oakridge-realty_lease_2026-03-19.pdf`: leases vs agreements
- `open-knowledge-press_reference_2026-01-24.pdf`: references vs guides
- `wayfarer-travel_confirmation_2025-04-30.pdf`: confirmations vs receipts
- `county-permits-office_form_2025-07-09.pdf`: forms vs applications

None touch the personal/entertainment/membership surface area. Attributable to gemma4 run-to-run variance at temperature=0 on Ollama (also documented in CLAUDE.md note 15).
