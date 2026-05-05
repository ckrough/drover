# Real-world evaluation corpus

This directory holds a small set of real-world PDFs (receipts, quotes, manuals, recipes, medical reports, shareholder letters, etc.) for evaluating drover's classifier against documents that carry **logos, embedded images, and graphical structure**, not just clean born-digital text.

It exists to test the hypothesis ADR-005's synthetic 80-doc corpus could not exercise: that real-world documents with vendor identity in logos and image-borne text benefit from Docling's OCR-aware structure parser. See [docs/adr/005-docling-evaluation.md](../../../docs/adr/005-docling-evaluation.md) §"What would change the decision." The `unstructured` fallback path described in older revisions of that ADR has since been removed by [ADR-006](../../../docs/adr/006-standardize-on-docling.md).

## Files

- `eval/ground_truth/real-world.jsonl` — JSONL ground-truth labels (one entry per PDF). **Local only; gitignored.** Filenames and extracted fields contain PII; this file must never be committed.
- `*.pdf` — the 14 real-world test documents (local only; not committed to git).

## Filling in the ground truth

Each entry has these fields:

| Field | Required | Notes |
|---|---|---|
| `filename` | yes | Must match the PDF in this directory exactly |
| `domain` | yes | One of the 16 canonical domains (see [`src/drover/taxonomy/household.py`](../../src/drover/taxonomy/household.py)) |
| `category` | yes | One of the canonical categories for that domain |
| `doctype` | yes | One of the 42 canonical doctypes |
| `vendor` | no | Full organization name as it appears on the document |
| `date` | no | `YYYYMMDD` (use `"00000000"` if no date applies) |
| `subject` | no | 2-4 lowercase words describing what the document is about |
| `notes` | no | Free-form annotation |

Stub entries with `"domain": ""`, `"category": ""`, or `"doctype": ""` will **fail** the eval until you fill them in. Pre-filled values reflect a quick read of the filename only — verify them against the document content.

Quick reference:

- **Domains** (16): `career`, `education`, `financial`, `food`, `government`, `household`, `housing`, `insurance`, `legal`, `lifestyle`, `medical`, `personal`, `pets`, `property`, `reference`, `utilities`
- **Doctypes** (42): `agreement`, `application`, `bill`, `certificate`, `confirmation`, `contract`, `deed`, `estimate`, `form`, `guide`, `identification`, `invoice`, `itinerary`, `journal`, `lease`, `letter`, `license`, `listing`, `manual`, `notice`, `offer`, `passport`, `paystub`, `permit`, `plan`, `policy`, `portfolio`, `presentation`, `quote`, `receipt`, `recipe`, `record`, `reference`, `referral`, `report`, `reservation`, `resume`, `return`, `statement`, `title`, `trust`, `warranty`, `will`
- **Categories per domain**: see `src/drover/taxonomy/household.py:CANONICAL_CATEGORIES`

## Running the eval

```bash
uv run drover evaluate \
  --ground-truth eval/ground_truth/real-world.jsonl \
  --documents-dir eval/samples/real-world \
  --ai-provider ollama --ai-model gemma4:latest
```

Docling (full-page OCR enabled) is the sole loader per [ADR-006](../../../docs/adr/006-standardize-on-docling.md).

## Sanity checks before running

```bash
# Confirm every PDF has a ground-truth entry and no stub fields remain
uv run python -c "
import json
from pathlib import Path
gt_path = Path('eval/ground_truth/real-world.jsonl')
pdf_dir = Path('eval/samples/real-world')
entries = [json.loads(l) for l in gt_path.read_text().splitlines() if l and not l.startswith('#')]
gt_files = {e['filename'] for e in entries}
pdf_files = {p.name for p in pdf_dir.glob('*.pdf')}
print('PDFs without ground truth:', pdf_files - gt_files)
print('Ground-truth entries without PDFs:', gt_files - pdf_files)
stubs = [e['filename'] for e in entries if not e.get('domain') or not e.get('category') or not e.get('doctype')]
print(f'Entries with stub required-fields: {len(stubs)}')
for f in stubs:
    print(f'  - {f}')
"
```

## Interpreting results

- **Vendor accuracy** is the load-bearing metric: real-world receipts/invoices typically encode vendor identity in logos and image regions. Docling's full-page OCR is what makes that text reachable.
- **Category accuracy** is the original axis ADR-005 measured. Flat synthetic data showed −3.8pp during evaluation; this corpus tells us whether structural cues help on real layouts.
- **Date and doctype accuracy** are sensitive to OCR transcription noise. If Docling's `force_full_page_ocr` setting (currently enabled in `src/drover/loader.py:_build_docling_converter`) corrupts dates by re-OCRing born-digital text, that is a known trade-off and may motivate switching to picture-region-only OCR.
