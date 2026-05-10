#!/usr/bin/env python3
"""One-shot labeller for the synthetic ground-truth `entity` column.

Reads `eval/ground_truth/synthetic.jsonl`, applies the entity labels
recorded in :data:`ENTITY_LABELS`, and writes the file back in place
preserving comment lines and ordering. Rows whose filename is not in
the label map are left untouched (no `entity` key emitted), so they
remain `entity: null` in the parsed `GroundTruthEntry` and are skipped
by the entity-accuracy metric.

The label set was produced by reading the first ~1200 chars of each
PDF in the entity-candidate domains (pets, medical, education,
lifestyle, entertainment) under prof-fes / ADR-007. Only documents
whose principal entity is non-vendor and not the document recipient
are labelled with a non-empty value.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

GROUND_TRUTH = Path("eval/ground_truth/synthetic.jsonl")

# Filename → expected entity. Empty string means "the model should
# return empty; nothing on this document qualifies as an entity per
# Rule 6". Filenames absent from this map are skipped (entity-accuracy
# is computed only over the labelled rows).
ENTITY_LABELS: dict[str, str] = {
    # Medical — patient names on the bill / referral.
    "riverbend-medical-center_invoice_2026-02-16.pdf": "Margaret L. Thornton",
    "riverbend-medical-center_invoice_2025-10-16.pdf": "Margaret L. Holloway",
    "greenwood-family-practice_invoice_2026-03-19.pdf": "Patricia M. Holloway",
    "greenwood-family-practice_referral_2025-06-11.pdf": "Harold T. Benson",
    # Pets — pet names on the boarding receipt.
    "wagging-tails-boarding_receipt_2026-03-23.pdf": "Biscuit",
    "wagging-tails-boarding_receipt_2025-05-24.pdf": "Biscuit",
    # No qualifying entity on the page — the model should return "".
    "medical_bill.pdf": "",  # patient ID only, no patient name
    "receipt.pdf": "",  # PetSmart retail receipt; no specific pet
    "summit-academy_agreement_2025-07-23.pdf": "",  # student name not filled in
    "summit-academy_report_2025-12-09.pdf": "",  # student reference id only
    "hillcrest-college_agreement_2025-12-07.pdf": "",  # undersigned recipient
    "hillcrest-college_agreement_2026-02-03.pdf": "",  # undersigned recipient
    "hillcrest-college_report_2026-04-06.pdf": "",  # vendor compliance report
    "pawsworth-supply_receipt_2025-06-27.pdf": "",  # customer name only, no pet
    "furry-friends-veterinary_agreement_2026-03-11.pdf": "",  # template, no pet
    # Lifestyle / travel itineraries — named human is the traveller
    # (recipient), excluded by the anti-recipient rule. The trip
    # itself is the subject; no performer/brand entity applies.
    "coastline-adventures_itinerary_2026-01-17.pdf": "",
    "greenleaf-tours_itinerary_2026-01-11.pdf": "",
    "wayfarer-travel_confirmation_2026-02-25.pdf": "",
    "wayfarer-travel_confirmation_2025-07-21.pdf": "",
    "wayfarer-travel_confirmation_2025-04-30.pdf": "",
}


def main() -> int:
    text = GROUND_TRUTH.read_text(encoding="utf-8")
    out_lines: list[str] = []
    updated = 0

    for raw in text.splitlines():
        line = raw.rstrip("\n")
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            out_lines.append(line)
            continue
        row = json.loads(stripped)
        filename = row.get("filename")
        if filename in ENTITY_LABELS:
            row["entity"] = ENTITY_LABELS[filename]
            updated += 1
            out_lines.append(json.dumps(row, ensure_ascii=False))
        else:
            out_lines.append(line)

    GROUND_TRUTH.write_text("\n".join(out_lines) + "\n", encoding="utf-8")
    print(f"Labelled {updated} rows with `entity`.")
    expected = len(ENTITY_LABELS)
    if updated != expected:
        print(
            f"WARNING: expected to label {expected} rows but only matched {updated};"
            " filename mismatches likely.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
