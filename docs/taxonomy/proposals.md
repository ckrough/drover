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

- `reference` — canonical category in 13 domains. Dual semantics (subject "reference materials about X" vs form "this IS a reference"). Needs corpus-driven analysis to disambiguate per domain. **Resolved in Round 3** (`d2bd890`); re-harvest 2026-05-03 confirms raw `reference` category emission is 0 across all domains.
- `contract` (legal) — no clean replacement category; a legal contract's subject is often the contract relationship itself. **Re-harvest 2026-05-03: 0/0 occurrences. Keep deferred.**
- `application` (career) — could redirect to `job_search`, but the category captures application-specific workflow distinct from broader job search activity. **Re-harvest 2026-05-03: 0/0 occurrences. Keep deferred.**
- `presentation` (career) — subject of a presentation varies; no clean replacement. **Re-harvest 2026-05-03: 0/0 occurrences. Keep deferred.**
- `recipe` (food) — the subject of a recipe document is the recipe itself; category and form genuinely coincide. **Re-harvest 2026-05-03: 0/0 occurrences. Keep deferred.**
- `reservation` (housing) — could redirect to `rental` for short-term bookings, but reservation carries timing/availability semantics that `rental` doesn't. **Re-harvest 2026-05-03: 1 → 0. No signal. Keep deferred.**

These may be revisited after a corpus expansion makes the relevant subject genuinely visible. The current 547-doc real-world corpus produces no signal for any of the four still-deferred straddlers.

## Item 7 — Co-occurrence sanity (analyzed 2026-05-02)

Both suspect tuples revisited using aggregate signal from the harvest. Verification done from `canonical_tuples` shape and `vendor_frequency` patterns; no document access required.

### `(financial, loan, reference)` x4 — resolved as plausible

The financial+loan corner of `canonical_tuples` has only two doctypes:

| Tuple | Count |
|-------|-------|
| `(financial, loan, reference)` | 4 |
| `(financial, loan, contract)` | 1 |

Top loan-related vendors in the corpus: `gmac-mortgage` (14), `american-education-services` (18) — both servicers that routinely send rate-change notices, annual disclosures, and terms summaries. Under the new subject-vs-form rule, `subject=loan, form=reference` is exactly right for "informational materials about a loan." Tuple is legitimate; no taxonomy fix.

### `(personal, correspondence, receipt)` x10 — sharpened hypothesis

Looking at all personal-domain tuples reveals `correspondence` is dominant as a *category*, not just for this tuple:

| Tuple | Count |
|-------|-------|
| `(personal, correspondence, receipt)` | 10 |
| `(personal, correspondence, confirmation)` | 6 |
| `(personal, correspondence, letter)` | 4 |
| `(personal, correspondence, report)` | 2 |
| `(personal, correspondence, invoice)` | 1 |
| `(personal, None, receipt)` | 5 |
| `(personal, None, confirmation)` | 5 |
| `(personal, membership, receipt)` | 3 |
| `(personal, travel, *)` | 9 (across 4 doctypes) |
| `(personal, identity, report)` | 1 |
| `(personal, membership, notice/letter)` | 2 |

23 of ~48 personal-domain tuples have `correspondence` as the category. That's not "this specific tuple is weird" — it's "`correspondence` is functioning as a fallback category when no specific personal subject fits." The form-receipt-on-correspondence-letter pattern is consistent with donation/dues/non-profit acknowledgements that the LLM struggles to slot into `membership`.

**Implication, not action:** `correspondence` is a candidate for the next refactor pass. It's canonical *category* in 6 domains (legal, education, personal, government, utilities, career) AND has the doctype alias `correspondence → letter`. By the new subject-vs-form rule, `correspondence` describes a form (a letter or note), not a subject. Demoting it from CANONICAL_CATEGORIES across all 6 domains would force the LLM to pick a real subject (`membership`, `identity`, etc.) and cleanly route the form to `letter`. This was not in scope for the Moderate hierarchy refactor and needs its own evidence + prompt-side coordination.

**Deferred to a future pass.** The aggregate signal is strong enough to name the next refactor target precisely; a ground-truth document spot-check would confirm whether the donation-acknowledgement hypothesis holds before any code change.

## Item 7 — applied (Round 2, correspondence demotion)

`correspondence` removed from `CANONICAL_CATEGORIES` in 6 domains (career, education, government, legal, personal, utilities). The doctype-layer routing (`correspondence → letter`) is unchanged — LLM-emitted correspondence forms continue to normalize to `letter`.

Per the no-"other" rule, no replacement aliases. When the LLM emits `correspondence` as a category, the result is `canonical: null` — a visible gap for ground-truth refinement.

Expected post-merge behavior (re-harvest signal):
- The 23 personal-domain `(personal, correspondence, *)` tuples should redistribute. Donation/dues acknowledgements should land on `(personal, membership, letter)`. Generic personal mail should surface as `(personal, null, letter)` — a real gap.
- Educational correspondence should redistribute among existing categories (`reference`, `transcript`) or surface as gaps.
- Government correspondence should redistribute toward `federal`/`state`/`local`.

Re-harvest verification (run `eval/runs/20260503-132742/`, ollama/gemma4, 532 processed): `(personal, correspondence, *)` cleared completely (23 → 0); raw `correspondence` category total dropped from 26 to 0 across the whole corpus. The donation/dues-to-membership hypothesis did not bear out: `(personal, membership, *)` stayed flat at 5 and `(personal, *, letter)` dropped from 5 to 3. The bulk landed on `(personal, expense, receipt)` (1 → 38, +37) and `(personal, expense, confirmation)` (0 → 14, +14), which is consistent with the receipts being expense-shaped rather than membership-shaped. The demotion is structurally correct; the predicted redistribution target was wrong.

## Item 7 — applied (Round 3, reference straddler resolution)

`reference` removed from `CANONICAL_CATEGORIES` in all 15 domains where it appeared (every domain except `reference` itself). The doctype layer is unchanged: `reference` remains in `CANONICAL_DOCTYPES`, and the form-sense aliases `article|list|webpage → reference` continue to route.

The four `documentation → reference` rows in `CATEGORY_ALIASES` (utilities, personal, property, insurance) are removed because they now point to a non-canonical target. LLM-emitted `category="documentation"` in those domains will surface as `canonical: null` until re-harvest evidence guides further action.

Per the no-"other" rule, no replacement aliases. When the LLM emits `category="reference"`, the result is `canonical: null` — a visible gap.

Driving evidence (533-doc harvest, ollama/gemma4):
- Subject sense (`category="reference"`): 33 raw emissions, 17 canonical. Distribution shows fallback usage — receipts/forms/statements landing on "reference" when a specific subject would fit (food expense, medical claim, government federal/state).
- Form sense (`doctype="reference"`): 11 raw and canonical. Stable, distributed across genuine reference works (loan terms summaries, generic articles).

Expected post-merge behavior (re-harvest signal):
- `(food, reference, receipt)` × 4 should redistribute to `(food, expense, receipt)`.
- `(medical, reference, *)` should redistribute to `(medical, expense|claim, *)`.
- `(government, reference, *)` should redistribute toward `federal|state|local`.
- Genuine subject-less reference works should surface as `(domain, null, reference)` — a real gap.
- The previously aliased `documentation → reference` cases (utilities, personal, property, insurance) will surface as drift; they were always thin signal.

Updates the structural test `test_no_canonical_category_is_also_canonical_doctype`: the `(d, "reference")` exception is removed from the `allowed` set across all domains.

Re-harvest verification (run `eval/runs/20260503-132742/`, ollama/gemma4, 532 processed): all eight target tuples cleared (food/medical/government/legal/housing/education/property/reference reference category total: 17 → 0). The raw `reference` category emission is 0 across the entire corpus (33 → 0). `(financial, loan, reference)` stayed at 4 as expected (legitimate form-sense). The previously aliased domains all stayed at thin signal (`(utilities, documentation, *)` 5 → 1, `(personal, documentation, *)` 1 → 2, `(property, documentation, *)` 1 → 1, `(insurance, documentation, *)` 1 → 0). The form-sense `(reference, documentation, reference)` rose from 2 to 13 (+11), absorbing the cases where the LLM previously emitted `(reference, reference, reference)`: this is the correct canonicalization, not a regression.

## Item 7 — re-harvest validation (Rounds 1+2+3 cumulative)

Re-runs `scripts/collect_classification_tuples.py` against the same `~/Documents/personal-archive` corpus that produced the 533-doc baseline at `eval/runs/20260501-152751/`. Confirms cumulative impact of the three demotion rounds: Round 1 (commit `3f259f1`, artifact-form terms), Round 2 (commit `5a69301`, correspondence), Round 3 (commit `d2bd890`, reference).

### Run metadata

| Field | Baseline (`20260501-152751`) | New (`20260503-132742`) | Δ |
|-------|-----------------------------|--------------------------|---|
| corpus_size | 547 | 547 | 0 |
| processed | 533 | 532 | -1 |
| errors | 14 | 15 | +1 |
| model | ollama/gemma4:latest | ollama/gemma4:latest | — |

Both within plan acceptance (processed ±10 of 533, errors ≤ 25).

### Headline deltas (top movers)

| Tuple | Base | New | Δ | Interpretation |
|-------|-----:|----:|--:|----------------|
| `(personal, expense, receipt)` | 1 | 38 | +37 | Round 2 absorption target. |
| `(personal, expense, confirmation)` | 0 | 14 | +14 | Round 2 absorption target. |
| `(property, payment, confirmation)` | 18 | 4 | -14 | Property-payment redirected toward `mortgage`. |
| `(utilities, payment, confirmation)` | 5 | 17 | +12 | Utility-payment consolidating. |
| `(reference, documentation, reference)` | 2 | 13 | +11 | Form-sense reference works canonicalize correctly. |
| `(food, purchase, receipt)` | 11 | 0 | -11 | Food domain shrank; receipts re-routed to `(personal, expense, receipt)`. |
| `(property, mortgage, confirmation)` | 7 | 17 | +10 | Property-payment redirected here. |
| `(personal, correspondence, receipt)` | 10 | 0 | -10 | Round 2 demotion target. |
| `(utilities, payment, receipt)` | 7 | 15 | +8 | Utility-payment consolidating. |
| `(reference, documentation, manual)` | 10 | 2 | -8 | Round 1 `manual` doctype demotion working. |

### Round 1 verification

Round 1 demoted `resume`, `manual`, `record`, `identification`, `agreement` (×7 domains), `plan` from `CANONICAL_CATEGORIES`.

| Hypothesis | Base | New | Δ | Verdict |
|------------|-----:|----:|--:|---------|
| `(*, agreement, *)` raw category cleared | 4 | 0 | -4 | PASS |
| `(*, plan, *)` raw category cleared | 1 | 0 | -1 | PASS |
| `(*, record, *)` raw category | 0 | 0 | 0 | PASS (already absent) |
| `(*, identification, *)` raw category | 1 | 0 | -1 | PASS |
| `(career, resume, *)` raw category | 1 | 0 | -1 | PASS |
| `(career, job_search, *)` redirect target | 0 | 1 | +1 | PASS (resume → job_search confirmed) |
| `(reference, manual, *)` raw category | 1 | 0 | -1 | PASS |
| `(reference, documentation, *)` redirect target | 21 | 27 | +6 | PASS (manual + reference absorbed here) |
| Doctype `manual` raw count | 13 | 3 | -10 | PASS (form-sense survives at low count) |

All hypotheses confirmed. The doctype `manual` retained legitimate form-sense usage at low frequency.

### Round 2 verification

Round 2 demoted `correspondence` from `CANONICAL_CATEGORIES` in 6 domains.

| Hypothesis | Base | New | Δ | Verdict |
|------------|-----:|----:|--:|---------|
| `(personal, correspondence, *)` cleared | 23 | 0 | -23 | PASS |
| `(utilities, correspondence, *)` cleared | 1 | 0 | -1 | PASS |
| `(financial, correspondence, *)` cleared | 1 | 0 | -1 | PASS |
| Raw `correspondence` category total | 26 | 0 | -26 | PASS |
| `(personal, membership, *)` should rise | 5 | 5 | 0 | FAIL (flat) |
| `(personal, membership, letter)` should rise | 1 | 1 | 0 | FAIL (flat) |
| `(personal, *, letter)` should rise | 5 | 3 | -2 | FAIL (slight drop) |

**Demotion succeeded; predicted redistribution target was wrong.** The cleared correspondence tuples landed primarily on `(personal, expense, receipt)` (+37) and `(personal, expense, confirmation)` (+14), which is consistent with the underlying documents being expense-shaped (paid for X) rather than membership/donation-shaped. No follow-up action: the redistribution is structurally clean.

### Round 3 verification

Round 3 demoted `reference` from `CANONICAL_CATEGORIES` in 15 domains and removed 4 `documentation → reference` aliases.

| Hypothesis | Base | New | Δ | Verdict |
|------------|-----:|----:|--:|---------|
| `(food, reference, *)` cleared | 4 | 0 | -4 | PASS |
| `(medical, reference, *)` cleared | 4 | 0 | -4 | PASS |
| `(government, reference, *)` cleared | 3 | 0 | -3 | PASS |
| `(legal, reference, *)` cleared | 1 | 0 | -1 | PASS |
| `(housing, reference, *)` cleared | 1 | 0 | -1 | PASS |
| `(education, reference, *)` cleared | 2 | 0 | -2 | PASS |
| `(property, reference, *)` cleared | 2 | 0 | -2 | PASS |
| `(financial, loan, reference)` stable | 4 | 4 | 0 | PASS (form-sense legitimate) |
| Raw `reference` category total | 33 | 0 | -33 | PASS |
| `(reference, reference, *)` form-sense | 1 | 0 | -1 | PASS (re-routed to documentation+reference) |

The form-sense reference works that previously emitted `(reference, reference, *)` now correctly canonicalize as `(reference, documentation, reference)`, which rose 2 → 13 (+11). This is the right normalization under the subject-vs-form rule.

### `documentation` follow-up status

Round 3 removed 4 `documentation → reference` aliases. Counts in the affected domains stayed below the promotion threshold (≥ 10 raw and clearly subject-genuine):

| Domain | Raw base | Raw new | Canon new | Verdict |
|--------|---------:|--------:|----------:|---------|
| utilities | 5 | 1 | 0 | Below threshold; leave as gap. |
| personal | 1 | 2 | 0 | Below threshold; leave as gap. |
| property | 1 | 1 | 0 | Below threshold; leave as gap. |
| insurance | 1 | 0 | 0 | Below threshold; leave as gap. |
| household | 10 | 5 | 5 | Already canonical; no change. |
| reference | 21 | 27 | 27 | Already canonical; primary home. |
| career | 1 | 1 | 1 | Already canonical; no change. |

**Verdict:** No promotion needed. The four newly-orphaned domains all settled below the threshold; the alias removal cleaned out fallback usage rather than masking a real subject.

### Straddler signal for the deferred five

Five straddlers carried forward from Item 2 (`contract`/legal, `application`/career, `presentation`/career, `recipe`/food, `reservation`/housing).

| Straddler | Base | New | Verdict |
|-----------|-----:|----:|---------|
| `(legal, contract, *)` | 0 | 0 | Keep deferred. No signal. |
| `(career, application, *)` | 0 | 0 | Keep deferred. No signal. |
| `(career, presentation, *)` | 0 | 0 | Keep deferred. No signal. |
| `(food, recipe, *)` | 0 | 0 | Keep deferred. No signal. |
| `(housing, reservation, *)` | 1 | 0 | Keep deferred. No signal. |

The 547-doc real-world corpus produces no measurable signal for any of the four still-deferred straddlers. None becomes a Round 4 candidate on this evidence.

### New drift surface

Tuples reaching count ≥ 5 in the new harvest that were below 5 in baseline:

| Tuple | Base | New | Read |
|-------|-----:|----:|------|
| `(personal, expense, receipt)` | 1 | 38 | Round 2 redistribution target. Healthy. |
| `(personal, expense, confirmation)` | 0 | 14 | Round 2 redistribution target. Healthy. |
| `(reference, documentation, reference)` | 2 | 13 | Round 3 form-sense re-routing. Healthy. |
| `(personal, travel, receipt)` | 1 | 7 | Travel cluster grew; legitimate. |
| `(personal, travel, confirmation)` | 4 | 7 | Travel cluster grew; legitimate. |
| `(financial, credit, report)` | 0 | 7 | Credit reports landing correctly (was masked by `reference`). |
| `(utilities, expense, bill)` | 3 | 6 | Utility expense canonical. Healthy. |
| `(housing, payment, confirmation)` | 0 | 6 | Healthy redistribution. |
| `(personal, travel, itinerary)` | 3 | 5 | Travel cluster. Healthy. |

All new high-count tuples are healthy redistributions, not drift. **No Round 4 candidate emerges.**

The drift section of the harvest aggregate (count ≥ 5) now contains only `unknown` token entries (43, 43, 43). Every other count-≥5 drift entry from the baseline has cleared.

### Decision matrix

| Item | Status |
|------|--------|
| Round 1 demotions (resume/manual/record/identification/agreement/plan) | CLOSE. All hypotheses verified. |
| Round 2 demotion (correspondence) | CLOSE. Demotion verified; redistribution target differed from prediction but is structurally correct. |
| Round 3 demotion (reference) | CLOSE. All hypotheses verified. |
| `documentation` promotion in utilities/personal/property/insurance | KEEP DEFERRED. All below promotion threshold in 547-doc corpus. |
| Straddler `contract` (legal) | KEEP DEFERRED. No signal. |
| Straddler `application` (career) | KEEP DEFERRED. No signal. |
| Straddler `presentation` (career) | KEEP DEFERRED. No signal. |
| Straddler `recipe` (food) | KEEP DEFERRED. No signal. |
| Straddler `reservation` (housing) | KEEP DEFERRED. No signal. |
| Round 4 implementation | NOT INDICATED. No corpus signal warrants further refactor. |
| External cross-reference (NARA, FamilySearch) | KEEP DEFERRED. Unblocked by this validation but not in scope. |
| Throwaway harvester `scripts/collect_classification_tuples.py` | FILE NEW BEADS TASK to delete. All rounds verified, no remaining open items rely on it. |

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

## Round 4 — applied (LCGFT/schema.org alignment)

**Goal:** align the doctype axis with LCGFT genre/form labels (plural folders)
and the schema.org transactional surface (aliases). Source: see
`docs/taxonomy/design-rationale.md` and `docs/taxonomy/external-mapping.md`.

### Changes

| Change | Detail |
|---|---|
| Pluralized all 41 canonical doctypes | LCGFT genre/form alignment: `receipt → receipts`, `invoice → invoices`, etc. Folders use plural. |
| Added `DOCTYPE_SINGULAR` map | `{plural: singular}`. `PathBuilder` calls `taxonomy.singular_form()` before passing doctype to the naming policy so filenames stay singular (one file = one instance). |
| Added `singular_form()` on `BaseTaxonomy` | Default falls back to input value when no mapping exists. |
| Dropped `contracts` doctype | LCGFT has no standalone Contracts term; specific instrument doctypes (`agreements`, `deeds`, `leases`, `titles`, `trusts`, `wills`) carry the load. `contract → agreements` alias added for backwards compatibility. |
| Demoted `recipe` from `food` categories | Schema.org Recipe is a CreativeWork (HowTo subtype); the doctype `recipes` carries the form. No replacement category. |
| Demoted `reservation` from `housing` categories | Schema.org Reservation is Intangible/transactional; the doctype `reservations` carries the form. No replacement category. |
| Dropped `contract` from `legal` categories | Legal categories now: `{court, estate}`. Full LCGFT Law-materials restructure deferred (no corpus signal). |
| Added `floor_plans`, `menus`, `maps` to canonical doctypes | LCGFT-recognized forms with plausible household occurrence. |
| Added 9 schema.org Reservation subtype aliases | `flight_reservation`, `lodging_reservation`, `food_establishment_reservation`, etc. → `reservations`. |
| Added schema.org transactional aliases | `order → receipts`, `ticket → reservations`, `tickets → reservations`. |
| Reorganized `DOCTYPE_ALIASES` with section headers | Singular→plural / schema.org subtypes / schema.org transactional / LCGFT-derived synonyms / empirically discovered. |
| Upgraded structural test to semantic comparison | Normalizes plural/singular before checking category-vs-doctype collisions, so `recipe` (category) and `recipes` (doctype) collide conceptually even when their strings differ. |
| Updated prompt Rule 5 examples to plurals | Worked examples cite `resumes`, `agreements`, `manuals`. No container framing or authority citation in the prompt itself (those are in `design-rationale.md` and `external-mapping.md`). |
| Updated `eval/ground_truth/synthetic.jsonl` doctypes | Singular → plural via `taxonomy.canonical_doctype()`. |

### Authority basis

- **LCGFT** (form/genre authority) for plural doctype labels and the
  form-vs-subject rule. See
  <https://www.loc.gov/aba/publications/FreeLCGFT/2020%20LCGFT%20intro.pdf>.
- **schema.org** (transactional/web-entity authority) for receipts/orders,
  reservations, listings, permits, certifications, maps, menus, recipes,
  reports.
- Per-line URI annotations in `src/drover/taxonomy/household.py`. Full
  mapping in `docs/taxonomy/external-mapping.md`.

### gemma4 pre-flight (Phase A0)

Ran a 20-document pre-flight on `eval/samples/synthetic/` (sample seed 42)
through `ollama / gemma4:latest` against the new plural canonical doctypes.
Source artifact: `eval/runs/round4-preflight/preflight-tuples.json`.

| Form | Count | Share |
|---|---|---|
| Plural (canonical) | 19 | 95.0% |
| Singular (alias-routed) | 1 | 5.0% |
| Other | 0 | 0.0% |

The single singular emission was `report` (one occurrence). Every other
emission landed directly on a plural canonical doctype (`manuals`,
`agreements`, `leases`, `reports`, `statements`, `certificates`,
`estimates`, `forms`, `guides`, `invoices`, `itineraries`, `policies`,
`warranties`).

**Interpretation:** gemma4 follows the plural taxonomy menu it sees in
`to_prompt_menu()`. The 5% singular tail is well below the 40% threshold
the plan flagged as concerning, and the singular→plural alias surface
absorbs it transparently. Post-merge harvester drift redistribution should
read normally (no spike in alias hits to misinterpret as regression).

### Anthropic prompt-cache invalidation

Round 4 invalidates the Anthropic prompt cache because the taxonomy menu
(plural doctype list) changes. One-time re-warm cost: roughly $0.50 for the
synthetic eval (94 docs) and ~$3 for a real-world re-harvest (533 docs). All
subsequent runs benefit from cache reuse on the unchanged menu.

### Round 4 verification (synthetic eval)

**Run artifacts:** `eval/runs/round4-parity-20260504-132642/` (initial, pre-remap grading) and `eval/runs/round4-parity-20260504-141532/` (post-remap grading). Model: `gemma4:latest` via Ollama. 80 synthetic PDFs.

**Ground-truth remap (19 rows):** the parity check surfaced that `eval/ground_truth/synthetic.jsonl` still encoded form-words as categories (`recipe`, `manual`, `agreement`, `correspondence`, `record`, `reference`) under Round 3 conventions. Round 4's form-vs-subject rule (categories name subjects, doctypes name forms) makes these uncanonical. Remapped to canonical subject categories per domain:

| Pattern | Count | Mapping |
|---|---|---|
| `food/recipe` (demoted) | 3 | `food/meal_plan` |
| `food/reference` (form-as-category) | 2 | `food/meal_plan` |
| `reference/manual` (form-as-category) | 3 | `reference/documentation` |
| `property/agreement` (form-as-category) | 4 | `property/{hoa, rental, maintenance}` (per vendor signal) |
| `property/reference` | 1 | `property/hoa` |
| `legal/reference` | 1 | `legal/estate` (trust doctype) |
| `household/reference` | 1 | `household/documentation` |
| `government/correspondence` | 1 | `government/state` |
| `education/{reference, agreement}` | 2 | `education/{financial_aid, transcript}` |
| `medical/record` | 1 | `medical/primary_care` |

All 80 rows now validate against `t.categories_for_domain(domain)`.

**Headline metrics (run2 vs Round 3 baseline `reference-demotion-post`):**

| Metric | Baseline | Round 4 (run2) | Delta | Flag |
|---|---|---|---|---|
| domain_accuracy | 0.8250 | 0.7625 | -6.25pp | REGRESSION |
| category_accuracy | 0.4875 | 0.5625 | +7.50pp | improvement |
| doctype_accuracy | 0.9500 | 0.9500 | 0.00pp | OK |
| vendor_accuracy | 0.8125 | 0.8250 | +1.25pp | OK |
| date_accuracy | 0.8125 | 0.8500 | +3.75pp | OK (WATCH band) |

Two back-to-back runs produced identical headline numbers, ruling out gemma4 non-determinism as the source of the domain drop.

**Domain regression cluster (5 flips):**

1. Recipe drag (3 of 5): `harvest-table-co-op_recipe`, `maple-lane-grocers_recipe`, `willowbrook-market_manual` all flip `food → reference`. Round 4 removed `recipe` from canonical `food` categories; gemma4 now classifies these as `reference/{other, documentation}` and the domain travels with the category. Synthetic ground truth still has `food` as the domain, so all three score as domain misses.
2. Government drift (2 of 5): `county-permits-office_form` (`government → property`) and `state-tax-authority_letter` (`government → financial`). No structural Round 4 cause; these are gemma reasoning artifacts on form-heavy government docs.

Excluding the recipe cluster, domain accuracy would land at 0.800 (-2.5pp, WATCH band). The category gain (+7.50pp) is the inverse of the same effect: post-remap, gemma's predictions match the cleaner subject-category truth labels much better.

**Verdict:** parity with caveat. The taxonomy change is structurally validated (doctype flat, category up sharply, vendor and date stable or up). The 6.25pp domain headline drop is dominated by a single explainable cluster (recipe demotion drag) plus 2-doc gemma variance on government forms. No alias-surface fix is appropriate per the plan's "do not improvise canonical doctypes" guidance; the recipe-domain drag is a Round 5 candidate (either a `food/recipes` recovery alias or per-doctype domain hints in the prompt).

**Round 5 follow-ups identified:**

- Recipe-domain drag: 3 synthetic recipe docs flip `food → reference` after the `food/recipe` demotion. Open question: does real-world corpus show the same cluster? Confirm via Phase H harvester re-run before deciding remediation.
- Government form drift: 2 docs flip to `property` and `financial`. Likely too small to act on without corpus signal; revisit after harvester.

### Round 4 verification (real-world harvester)

**Run artifact:** `eval/runs/round4-realworld-20260504-160829/realworld-tuples.json`. Model: `gemma4:latest` via Ollama. Corpus: `~/Documents/personal-archive`, 547 docs, 532 processed (15 errors). Baseline: `eval/runs/20260501-152751/realworld-tuples.json` (Round 3 cumulative, 533 processed).

**Drift redistribution (the headline metric):**

| Field | Baseline | Round 4 | Delta |
|---|---:|---:|---:|
| Drift entries (total) | 53 | 32 | -21 (-40%) |
| Category drift (sum of counts) | 226 | 74 | -152 (-67%) |
| Top category-drift residual | `payment` (65) | `unknown` (43) | `payment` cleared to 7 |

The category-drift cleanup is the largest single improvement. `payment` collapsed from 65 cross-domain emissions (property: 21, education: 19, utilities: 12, medical: 10, others) to 7 (only personal: 6, political: 1). `documentation` (29 → 8), `purchase` (25 → 4), `transfer` (9 → 1), `reference` (16 → 0), `correspondence` (3 → 0), and `agreement` (4 → 0) all cleared or shrank substantially. None of the cleared categories are Round 4 changes per se; the cleanup reflects cumulative Rounds 1-3 demotions absorbing into the menu plus the alias surface routing more raw terms.

**Recipe and reservation impact:**

| Term | Where | Baseline | Round 4 |
|---|---|---:|---:|
| `recipe` | category emissions | 0 | 0 |
| `recipe` / `recipes` | doctype emissions | 0 | 0 |
| `reservation` | category emissions | 1 | 1 |
| `reservations` | doctype emissions | n/a | 1 |

**The recipe corpus signal is zero.** The personal archive contains no recipe documents. The synthetic recipe-domain drag (3 docs flipping `food → reference`) has no real-world counterpart on this corpus. This deflates urgency on the Round 5 recipe-domain drag question: it appears to be a synthetic-corpus artifact triggered by template recipe documents that don't represent the real-world distribution. Reservation has 1 doc and is unchanged.

**Schema.org defensive additions:**

| Alias | Round 4 emissions on this corpus |
|---|---:|
| `flight_reservation`, `lodging_reservation`, `food_establishment_reservation`, `event_reservation`, `rent_reservation`, `reservation_package`, `taxi_reservation`, `train_reservation`, `bus_reservation` | 0 each |
| `floor_plans`, `menus`, `maps` (LCGFT gap-fills) | 0 each |
| `order` / `orders` (schema.org transactional) | 0 each |
| `tickets → reservations` (schema.org transactional) | 1 (resolved canonical via alias) |

The 9 schema.org Reservation subtypes are inert on this corpus. gemma4 emits `reservations` directly when it sees a reservation-shaped document; it does not decompose to subtypes. The LCGFT gap-fills (`floor_plans`, `menus`, `maps`) are also inert on this corpus. Defensive additions were costless but produced no measurable improvement here. The single `tickets → reservations` hit absorbed the one entry that was previously `doctype/ticket → null` drift in the baseline. The transactional alias surface earned its keep on exactly that one document.

**Singular emission rate (the surprise):**

| Form | Baseline | Round 4 |
|---|---:|---:|
| Plural canonical doctypes | 0 (0%) | 292 (60%) |
| Singular emissions (alias-routed) | 484 (100%) | 195 (40%) |

The Phase A0 synthetic pre-flight saw 95% plural / 5% singular. Real-world is 60% plural / 40% singular, right at the plan's "concerning" 40% threshold. The 40% singular tail is dominated by one term: `confirmation` (154 of 195 singular emissions = 79%). gemma4 reads "Confirmation" verbatim from document headers far more often than it picks `confirmations` from the menu. Other top singular emissions: `receipt` (21), `statement` (11), `bill` (5), `notice` (4). The singular→plural alias surface absorbs all of this transparently; no canonical-doctype gaps result. The gap between synthetic (5%) and real-world (40%) is itself the finding: synthetic templates underestimate how strongly real documents anchor gemma to their own header language.

**Verdict:** parity with substantial improvement. Drift down 40% by entry count and 67% by category emission count. No new high-count drift entries above 5. The recipe-domain drag concern from synthetic does not generalize: the corpus has no recipes. Schema.org subtype aliases are dead weight on this corpus but cost nothing to keep.

**Updated Round 5 candidates (post real-world):**

- Singular tail (40%, mostly `confirmation`): real but absorbed transparently. Open question is whether to strengthen the prompt to prefer plural forms (reducing alias dependence) or accept the alias surface as the long-term solution. Cost-of-action vs cost-of-status-quo is genuinely close; depends on whether other models (anthropic, openai) show the same singular preference.
- Recipe-domain drag: deprioritized. Synthetic-only signal; no real-world docs to validate a fix against.
- `unknown` emissions (43 docs, 8% of corpus): persistent across rounds. Suggests a prompt-side investigation (forbid `unknown`, force closest canonical) or an acknowledgement that 8% of household documents are genuinely unclassifiable.
- `documentation` as category in non-{household, reference} domains (8 emissions, persistent): low-volume residual; revisit if it grows.
