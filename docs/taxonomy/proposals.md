# Household Taxonomy: Improvement Proposals

**Source artifact:** `eval/runs/20260501-152751/realworld-tuples.json` (533 docs processed, 14 errors, ollama/gemma4:latest, household taxonomy).

**Guiding rule:** Per [feedback memory](~/.claude/projects/-Users-ckrough-Code-open-source-drover/memory/feedback_taxonomy_no_other.md), do not introduce `"other"` or any catch-all canonical. Leave gaps visible (`drift[].canonical: null`) for ground-truth refinement later.

## Headline drift signals

Drift counts where canonical resolves to `null` (excluding LLM `"unknown"` outputs which the user has explicitly elected to keep as gaps):

| Field    | Domain     | Raw term         | Count | Action                                |
|----------|------------|------------------|-------|---------------------------------------|
| category | property   | payment          | 21    | promote `payment` to property canon   |
| category | reference  | documentation    | 21    | promote `documentation` to ref canon  |
| category | education  | payment          | 19    | promote `payment` to education canon  |
| category | food       | purchase         | 12    | alias `purchase`→`expense` (food)     |
| category | utilities  | payment          | 12    | promote `payment` to utilities canon  |
| category | medical    | payment          | 10    | promote `payment` to medical canon    |
| category | financial  | reference        | 9     | promote `reference` to financial canon|
| category | utilities  | expense          | 9     | promote `expense` to utilities canon  |
| category | utilities  | documentation    | 5     | alias `documentation`→`reference`     |
| category | property   | purchase         | 5     | alias `purchase`→`expense` (property) |
| category | personal   | purchase         | 5     | alias `purchase`→`expense` (personal) |
| category | lifestyle  | reference        | 3     | promote `reference` to lifestyle canon|
| category | pets       | reference        | 2     | promote `reference` to pets canon     |
| category | financial  | agreement        | 2     | promote `agreement` to financial canon|
| category | housing    | agreement        | 2     | promote `agreement` to housing canon  |
| category | housing    | payment          | 2     | promote `payment` to housing canon    |
| category | lifestyle  | purchase         | 2     | alias `purchase`→`expense` (lifestyle)|
| domain   | (any)      | vehicle          | 1     | alias `vehicle`→`household`           |

Single-occurrence drift (`billing`, `gift_giving`, `traveling`, `dispute`, etc.) is addressed selectively where a clear synonym exists; the rest are left as gaps.

## Item 1 — Alias-pressure cleanup

### `payment` is a cross-cutting concept

`payment` is canonical only in `financial`. The data shows the LLM uses it across `property`, `education`, `utilities`, `medical`, `housing`, `insurance` for any bill/fee/receipt scenario — 65 unmapped occurrences total.

**Action:** Add `payment` as canonical to property, education, utilities, medical, housing, insurance. Pattern matches existing `expense`/`agreement` cross-domain canonicals.

### `reference` is a cross-cutting concept

`reference` is canonical in 11 of 16 domains. Drift shows the LLM also uses it in `financial` (9), `lifestyle` (3), `pets` (2), `personal` (1) where it's not yet canonical.

**Action:** Add `reference` as canonical to financial, lifestyle, pets, personal, insurance, utilities. (`reference` domain itself does not currently expose `reference` as a category — handled separately under documentation.)

### `documentation` ≈ `reference` for the LLM

The LLM uses `documentation` interchangeably with `reference`: 28 unmapped occurrences across 5 domains, plus `documentation` is canonical in `career` and `household` but `reference` is also canonical in those domains. Two synonyms competing for the same slot.

**Action:**
- Add `documentation` as canonical to the `reference` domain (where the concept is the domain's purpose).
- Alias `documentation` → `reference` for `utilities`, `personal`, `property`, `insurance` (after `reference` is added there).
- Leave `career` and `household` untouched for now (both terms canonical there is intentional, low-signal drift).

### `purchase` (singular) is missing from the alias map

`CATEGORY_ALIASES` maps plural `purchases` → `expense` for several domains, but the LLM emits the singular `purchase` 25 times across food (12), property (5), personal (5), lifestyle (2), career (1).

**Action:** Add `purchase` → `expense` aliases for food, property, personal, lifestyle, career. (Household keeps `purchase` as canonical — it's a real distinct category there.)

### `expense` gap in utilities

`expense` is canonical in 7 domains but not utilities. 9 unmapped occurrences.

**Action:** Add `expense` as canonical to utilities.

### `agreement` gaps in financial and housing

`agreement` is canonical in 6 domains; financial (loan agreements) and housing (lease/purchase agreements) are missing it.

**Action:** Add `agreement` as canonical to financial and housing.

### `correspondence` gap in utilities

Single occurrence but the concept is real (rate-change letters from utility companies).

**Action:** Add `correspondence` as canonical to utilities.

### Domain-level: singular `vehicle`

`DOMAIN_ALIASES` maps `vehicles` → `household` but not the singular form.

**Action:** Add `vehicle` → `household`.

### Synonym aliases (1-2 occurrence cleanup)

- `traveling` → `travel` for personal, lifestyle (2 total).
- `billing` → `payment` for insurance, medical (2 total).
- `gift_giving` → `expense` for lifestyle (1).

These are inexpensive aliases that match clear LLM word-choice variations.

## Item 2 — Hierarchy consistency (partially applied 2026-05-02)

**Status:** Moderate-scope refactor applied. See "Item 2 — applied" below for the change set. The remaining straddlers (`reference` plus five newly discovered ones) are documented under "Deferred straddlers".

### Original drift evidence

Several terms appeared at both `category` and `doctype` layers. The harvest showed the LLM was happy to put the same word in both slots:

| Tuple                                       | Count |
|---------------------------------------------|-------|
| `(reference, manual, manual)`               | 1     |
| `(career, resume, resume)`                  | 1     |
| `(financial, agreement, agreement)`         | 1     |
| `(reference, documentation, manual)`        | 10    |
| `(reference, documentation, reference)`     | 2     |
| `(financial, reference, reference)`         | 3     |
| `(pets, reference, reference)`              | 2     |

A clean rule (categories = subject, doctypes = artifact form) pushes the form-only terms to doctype-only.

## Item 2 — applied

The following six terms are demoted from `CANONICAL_CATEGORIES` and remain canonical doctypes:

| Term | Removed from category in | Replacement |
|------|--------------------------|-------------|
| `resume` | career | alias `(career, resume) → job_search` |
| `manual` | reference | alias `(reference, manual) → documentation` |
| `record` | medical | gap (drift surfaces for ground-truth refinement) |
| `identification` | legal | gap |
| `agreement` | financial, property, education, career, household, pets, housing | aliases `(property, agreement) → mortgage`, `(housing, agreement) → rental`; other domains gap |
| `plan` | household | gap |

**Prompt change:** `src/drover/prompts/classification.md` Rule 5 now states the subject-vs-form distinction explicitly with three worked examples (resume, agreement, manual) targeting the exact collision tuples above.

**Alias cleanup (CATEGORY_ALIASES):** −11 obsolete rows (the `*_records → record` and `contracts → agreement` chains targeting demoted categories), +4 new rows (`resume`, `manual`, `agreement` redirects above).

**Structural test:** `tests/test_taxonomy.py::TestHouseholdHierarchyRule::test_no_canonical_category_is_also_canonical_doctype` codifies the rule and prevents regressions. Documented exceptions are listed inline in the test's `allowed` set with rationale per pair.

### Deferred straddlers

Discovered during the structural-test pass; left as exceptions for now per the no-"other"/no-forced-fit rule:

- `reference` — canonical category in 13 domains. Dual semantics (subject "reference materials about X" vs form "this IS a reference"). Needs corpus-driven analysis to disambiguate per domain.
- `contract` (legal) — no clean replacement category; a legal contract's subject is often the contract relationship itself.
- `application` (career) — could redirect to `job_search`, but the category captures application-specific workflow distinct from broader job search activity.
- `presentation` (career) — subject of a presentation varies; no clean replacement.
- `recipe` (food) — the subject of a recipe document is the recipe itself; category and form genuinely coincide.
- `reservation` (housing) — could redirect to `rental` for short-term bookings, but reservation carries timing/availability semantics that `rental` doesn't.

These may be revisited after re-harvest reveals which (if any) are sources of ongoing LLM confusion.

## Item 7 — Co-occurrence sanity (FLAG, defer)

Two tuples that look semantically wrong:

- `(personal, correspondence, receipt)` — 10 occurrences. "Correspondence" plus "receipt" is an unusual combination; likely the LLM is forcing personal-domain documents into the only canonical category that fits and falling back to receipt as a generic doctype. Without document access we can't tell whether these are genuinely personal correspondence with receipt artifacts or misclassifications.
- `(financial, loan, reference)` — 4 occurrences. Plausible (loan reference materials) but worth verifying with ground truth.

**Deferred:** flagged for ground-truth refinement.

## Item 5 — External cross-reference (deferred to follow-up)

Per the plan's Step 5 ordering, external cross-reference happens after the post-proposal taxonomy stabilizes. Will run in a follow-up pass.

## Gaps deliberately left visible

These drift entries are real gaps the user wants to see, not absorbed into a catch-all:

- `domain: unknown` (46), `category: unknown` (46), `doctype: unknown` (45) — LLM-emitted "unknown" tokens. Suggests prompt-side investigation: should the prompt forbid "unknown" and force the LLM to pick the closest canonical, or is "unknown" a valid signal of unclassifiable content?
- `domain: political` (1), `(political, correspondence, receipt)` (1) — political domain candidate; vendor frequency shows `actblue` and `the-democratic-national-committee-dnc`. Insufficient evidence to add a domain.
- Single-occurrence categories without an obvious synonym: `dispute`, `conference`, `plan`, `billing_statement`, `goods` (in pets), `compensation` (in personal), `financial_aid` (in medical), `retirement` (in medical), `training` (in education), `membership` (in career).
- `doctype: ticket` (1) — travel ticket. Add later if frequency rises.

## Verification

After applying:

1. `uv run pytest tests/test_taxonomy.py` — existing tests are mechanism-level (case-insensitive lookup, sorted output, unknown→None) and will pass.
2. `uv run ruff check src/ && uv run ruff format src/`
3. `uv run mypy src/`
4. Re-render `to_prompt_menu()` and read it.
5. Optional: re-run the harvester on the same corpus and compare drift counts. Expected: the headline-table entries above drop to zero or near-zero; total `canonical: null` count (excluding "unknown") drops by ~155.
