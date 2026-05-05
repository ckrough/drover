# Taxonomy Design Rationale

## Form vs subject (LCGFT alignment)

Drover's structural rule — **categories name subjects, doctypes name forms; a
term cannot be canonical at both layers** — mirrors the foundational design
principle of LCGFT, the Library of Congress Genre/Form Terms vocabulary.

LCGFT distinguishes:

- **Form/genre**: what the document **is** (a manual, a recipe, a will).
- **Subject**: what the document is **about** (a topic, an activity, a thing).

LCGFT records form/genre exclusively; subjects live in LCSH (Library of
Congress Subject Headings). The 2020 LCGFT introduction documents this design
principle:
<https://www.loc.gov/aba/publications/FreeLCGFT/2020%20LCGFT%20intro.pdf>.

Drover's three-axis design (`domain × category × doctype`) follows the same
split: doctypes are the form axis, categories the subject axis within a
domain. The structural test in `tests/test_taxonomy.py` enforces the
non-collision invariant; documented straddlers must justify the exception.

## Doctype as container (Round 4)

Round 4 adopts plural canonical doctypes for the folder layer (LCGFT genre
alignment). The conceptual reframing:

- LCGFT's "Cookbooks" is the genre; an individual cookbook (or recipe) is an
  instance.
- Drover's `recipes/` is the folder; the files inside are individual recipe
  instances.

Filenames keep the singular form because one file represents one instance.
The split is implemented in `BaseTaxonomy.singular_form()` and applied by
`PathBuilder` before passing the doctype to the naming policy.

## schema.org for transactional surface

Schema.org provides the transactional and web-entity vocabulary that LCGFT
does not cover well:

- `Invoice`, `Order`, `Reservation`, `Ticket`, `Permit`, `RealEstateListing`,
  `Certification`, `Map`, `Menu`, `Recipe`, `Report`.

Where schema.org commits to a term Drover already uses, the source is cited
in `external-mapping.md`. Where schema.org defines subtypes (`Reservation`
has 9 children), the subtypes are accepted as `DOCTYPE_ALIASES` rather than
expanded into the canonical axis — Drover keeps the doctype axis flat for
end-user comprehensibility.

## Evidence-first precedent

The taxonomy expands and contracts based on **corpus signal**, not authority
weight. LCGFT's Law-materials hierarchy (`legal_instruments`, `claims`,
`court_records`, `statutes`) is richer than Drover's current `legal: {court,
estate}` categories; the restructure is deferred until corpus signal warrants
it. This precedent is documented in earlier rounds (see
`docs/taxonomy/proposals.md`) and constrains the scope of every alignment
round.

## Authority weighting (Round 4)

When two sources offer competing terms:

1. **Form/genre questions → LCGFT.** Doctype labels and the structural rule.
2. **Transactional/web-entity questions → schema.org.** Receipts/orders,
   reservations, listings, permits.
3. **Empirical drift → corpus.** Promote, alias, or demote based on observed
   frequency in the harvested real-world corpus.

When all three are silent, document the gap in `external-mapping.md` rather
than inventing a private term.
