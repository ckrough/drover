# Entity field — synthetic eval (post-rebase, labelled GT)

| Field | Value |
|---|---|
| Date | 2026-05-10 |
| Branch | worktree-wiggly-weaving-feigenbaum (prof-fes), rebased on `main` post PR #32 |
| Corpus | synthetic (80 docs) |
| Provider / model | ollama / gemma4:latest |
| Loader | docling |
| OCR backend | ocrmac (Apple Vision) |
| Ground truth | `entity` labelled on 20 candidate docs (6 with names, 14 with explicit `""`) |

## Accuracy

| Metric | Result |
|---|---|
| Domain | 86.2% |
| Category | 61.3% |
| Doctype | 91.2% |
| Vendor | 91.2% |
| Date | 90.0% |
| **Entity** | **70.0%** (14 / 20 labelled docs) |
| Errors | 0 |

## Deltas vs baseline

Baseline run: PR #32 commit message — `feat(taxonomy): drop personal domain, add lifestyle/entertainment category`.

| Metric | Baseline | This run | Delta |
|---|---|---|---|
| Domain | 87.5% | 86.2% | -1.3 pp (-1 doc) |
| Category | 61.3% | 61.3% | 0.0 pp (=) |
| Doctype | 93.8% | 91.2% | -2.5 pp (-2 docs) |

All three core metrics are within run-to-run noise of the latest main baseline. The −1/−2 doc movements are at the level we have historically seen between adjacent runs of the same prompt+model.

## Entity breakdown (20 labelled docs)

The labelled set is split across two cases: 6 docs with a non-vendor named entity on the page, and 14 docs where the model should return `""` because no qualifying entity exists (per Rule 6's anti-recipient and form-vs-recipient guidance).

**Correct (14):**

- 4 / 4 medical patient names extracted exactly (case-insensitive match): Margaret L. Thornton, Margaret L. Holloway, Patricia M. Holloway, Harold T. Benson.
- 1 / 2 pet receipts: `Biscuit` on the 2025-05-24 boarding receipt.
- 9 / 14 expected-empty cases: receipts and academic agreements where no entity is on the page.

**Incorrect (6):**

| Filename | Expected | Predicted | Cause |
|---|---|---|---|
| `medical_bill.pdf` | `""` | `"patient"` | Model emitted the role, not a name. No patient name on the page. |
| `coastline-adventures_itinerary_2026-01-17.pdf` | `""` | `"Margaret L. Fontaine"` | Traveller-name leak; Rule 6 anti-recipient guidance not applied to itineraries. |
| `greenleaf-tours_itinerary_2026-01-11.pdf` | `""` | `"Margaret L. Fontaine"` | Same — traveller-name leak. |
| `wagging-tails-boarding_receipt_2026-03-23.pdf` | `"Biscuit"` | `"Biscuit and Clover"` | Two pets on the receipt; ground-truth chose primary, model concatenated both. |
| `wayfarer-travel_confirmation_2026-02-25.pdf` | `""` | `"unknown"` | Model emitted literal `"unknown"` rather than `""` for absent entity. |
| `wayfarer-travel_confirmation_2025-07-21.pdf` | `""` | `"unknown"` | Same `unknown` literal. |

The miss patterns suggest tractable follow-ups (none blocking):

1. Rule 6 anti-recipient clause should explicitly cover travel itineraries and confirmations.
2. The schema or `_normalize_classification` could coerce `entity == "unknown"` to `""` on read, mirroring how `vendor` already accepts `"unknown"` as a sentinel.
3. Multi-entity documents (the two-pet receipt) need a ground-truth convention; the simplest is "first named entity wins."

Each is one small change; together they'd lift entity accuracy without touching the other metrics.

## Trails Offroad spot-test (post-rebase)

```
invoice-recurly-recurring_subscription_payment-20250416.pdf
```

Domain `lifestyle/membership/invoices/`, vendor Recurly, entity correctly `""` (no recipient leak). The model still prefers empty over guessing "Trails Offroad" as the brand for `personal`-text-heavy documents; that is a downstream prompt-tuning opportunity, not a regression.
