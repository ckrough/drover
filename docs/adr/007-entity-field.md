# ADR-007: Add Optional `entity` Field to the Filename Schema

## Status

Accepted (2026-05-10).

## Context

The pre-existing filename schema is `{doctype}-{vendor}-{subject}-{YYYYMMDD}.{ext}`. It captures form, issuer, topic, and date but loses the *named entity* the document is fundamentally about: the pet on a vet invoice, the patient on a medical bill, the performer on a concert reservation, the brand on a subscription invoice.

Concrete failure: a Trails Offroad subscription invoice classifies as `lifestyle/membership/invoices/invoice-recurly-subscription_service_billing-20250416.pdf`. The brand the subscription is *for* (Trails Offroad) appears nowhere in the leaf filename; only the billing platform vendor (Recurly) does. A user scanning their `lifestyle/membership/invoices/` folder cannot tell at a glance which subscription each invoice is for.

The same gap shows up across domains: `pets`, `medical`, `lifestyle`, `entertainment`, `subscriptions`, and `memberships` all want a "principal entity" slot that is distinct from the issuing vendor.

## Decision

Add a sixth optional classification field, `entity`, capturing the principal named entity of the document.

The new filename pattern is:

```
{doctype}-{vendor}-{subject}-{entity}-{YYYYMMDD}.{ext}
```

The entity slot is dropped when:

1. The classifier returns an empty string.
2. The normalized entity equals the normalized vendor (vendor/entity dedup).
3. The document's domain is in the redact list (default: `["medical"]`).
4. The user passed `--no-entity` to `drover organize`.

Folders remain taxonomic and unchanged; only the leaf filename is affected.

### Open design questions, resolved

| # | Question | Resolution |
|---|----------|------------|
| 1 | Field name (`entity` vs `target` vs `principal`) | `entity` — distinguishes from the existing `subject` topic field and reads naturally for pets, people, performers, and brands. |
| 2 | Suppress entity when it matches vendor? | Yes (default). Suppression happens in the naming policy, after both values are normalized. |
| 3 | Privacy redaction for personally-identifying entity values | Configurable list `naming_redact_entity_in_domains` (default `["medical"]`). When the document's domain is in the list, the entity slot is suppressed at filename-generation time. The classifier still produces and returns the entity for downstream consumers (e.g. macOS Finder tags) so it remains available outside the filesystem layer. |

### Component-budget check

NARA cap is 40 chars/component. Five components × 40 + 4 separators = 204 + ext, under the 255-byte filename limit. No length adjustment needed.

## Implementation

| Concern | Where it lives |
|---------|---------------|
| Schema | `src/drover/models.py` — `RawClassification.entity: str = ""` and `ClassificationResult.entity: str = ""`. |
| Prompt | `src/drover/prompts/classification.md` — Rule 6 (Principal Entity Identification) with per-domain guidance, plus a new step in the thinking checklist. |
| Naming | `src/drover/naming/base.py` adds `entity: str = ""` to `format_filename`. `src/drover/naming/nara.py` inserts the slot before the date and applies the vendor/entity dedup after normalization. |
| Path builder | `src/drover/path_builder.py` — `PathBuilder` accepts `emit_entity: bool` and `redact_entity_in_domains: list[str]` and applies suppression before delegating to the naming policy. |
| Classifier | `src/drover/classifier.py` — `_parse_response` accepts entity as optional (null/missing → `""`), and `_normalize_classification` threads it through. |
| Service wiring | `src/drover/service.py` — `ClassificationService` constructs `PathBuilder` with the new config knobs. |
| Config | `src/drover/config.py` — `naming_emit_entity: bool = True` and `naming_redact_entity_in_domains: list[str] = ["medical"]`. |
| CLI | `src/drover/cli.py` — `drover organize --no-entity` toggles `naming_emit_entity`; `entity` is added to `VALID_TAG_FIELDS` so Finder-tag flows can use it. |
| Eval | `src/drover/evaluation.py` — `GroundTruthEntry.entity`, `ClassificationComparison.entity_correct`, and a new `EvaluationResult.entity_accuracy` metric reported in both summary and JSON output. Existing accuracy metrics are unchanged. |
| Tests | `tests/test_models.py`, `tests/test_naming.py`, `tests/test_path_builder.py`, `tests/test_classifier_parse.py` — present/absent/duplicate-with-vendor cases, redaction by domain, `--no-entity`-equivalent path-builder flag, and parser entity-null/missing handling. |

## Consequences

- Existing downstream consumers that read `ClassificationResult.entity` get an empty string until the prompt change starts populating the field. No breaking change.
- Existing ground-truth entries without `entity` continue to evaluate cleanly: `entity_accuracy` is reported as `null` until ground truth is updated.
- The structured-output schema picks up an extra optional field. Pydantic defaults handle backward compatibility for cached or older responses.
- Privacy default: medical-domain documents do **not** carry the entity in their filenames out of the box. To opt out, drop `medical` from `naming_redact_entity_in_domains`.
- The `--no-entity` flag preserves a one-line escape hatch for users who prefer the legacy four-component filename.

## Alternatives considered

- **No new field; reuse `subject`.** Conflates the topical subject ("annual checkup") with the named entity ("Sally"). The two answer different questions and frequently both belong on the filename.
- **Always emit entity, no dedup.** Produces redundant filenames like `invoice-trails_offroad-subscription_billing-trails_offroad-20250416.pdf`. Rejected.
- **Folder-level entity (e.g. `pets/sally/medical/invoices/...`).** Mixes taxonomic structure with per-instance identity and explodes the folder count. The named entity is filename-level signal.

## References

- Ground-truth schema in `eval/ground_truth/synthetic.jsonl` gains an optional `entity` column.
- `CLAUDE.md` note 11 (Taxonomy section) records the schema change.
