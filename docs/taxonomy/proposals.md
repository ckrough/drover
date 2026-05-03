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
