# External Authority Cross-Reference

Maps every Drover canonical doctype to its primary external authority and any
schema.org transactional or web-entity counterpart. Open-source contributors
read this first when extending the taxonomy.

**Authorities:**

- **LCGFT** — Library of Congress Genre/Form Terms.
  Index: <https://id.loc.gov/authorities/genreForms.html>.
  LCGFT records *form/genre* (what the document **is**), parallel to Drover's
  doctype axis.
- **schema.org** — Schema.org vocabulary.
  Index: <https://schema.org/docs/full.html>.
  schema.org records *transactional and web-entity* types, useful for the
  receipts/orders/reservations/listings/permits cluster.

**Relationship codes:**

- *exact* — the term names the same form.
- *broader* — the authority term subsumes Drover's term.
- *narrower* — Drover's term is one form within the authority's broader term.
- *gap* — no clean external authority; documented gap.

| Drover doctype (plural / folder) | Singular (filename) | LCGFT | schema.org | Relationship | Notes |
|---|---|---|---|---|---|
| agreements | agreement | Legal instruments (under Records (Documents)) | — | broader | Round 4: absorbs the prior `contracts` doctype and the `contract` alias. |
| applications | application | — | — | gap | Deferred straddler; no authority commits. |
| bills | bill | — | — | gap | Aliased pattern with invoices. |
| certificates | certificate | — | <https://schema.org/Certification> | exact | |
| confirmations | confirmation | — | — | gap | Documented gap; no clean external authority. |
| deeds | deed | LC subject heading "Deeds" | — | exact | |
| estimates | estimate | — | — | gap | |
| floor_plans | floor_plan | LCGFT "Floor plans" (under Informational works) | — | exact | Round 4 addition. |
| forms | form | LCGFT "Blank forms" | — | broader | |
| guides | guide | LCGFT gf2014026108 (Guidebooks) | — | exact | |
| identifications | identification | — | — | gap | |
| invoices | invoice | — | <https://schema.org/Invoice> (Intangible) | exact | |
| itineraries | itinerary | — | — | gap | |
| journals | journal | LCGFT gf2014026085 (Diaries) | — | broader | |
| leases | lease | — | — | gap | |
| letters | letter | LCGFT gf2014026141 (Personal correspondence) | — | exact | |
| licenses | license | — | — | gap | |
| listings | listing | — | <https://schema.org/RealEstateListing> | narrower | schema.org type covers real-estate listings; Drover broadens to job/marketplace listings. |
| manuals | manual | LCGFT gf2014026109 (Handbooks and manuals) | — | exact | |
| maps | map | LCGFT gf2011026387 (Maps) | <https://schema.org/Map> | exact | Round 4 addition. |
| menus | menu | LCGFT "Menus" | <https://schema.org/Menu> | exact | Round 4 addition. |
| notices | notice | — | — | gap | Adversarial/regulatory connotation; functionally distinct from letters. |
| offers | offer | — | <https://schema.org/Offer> (price/availability, not the offer document) | broader | schema.org Offer is metadata, not the artifact. |
| passports | passport | — | — | gap | |
| paystubs | paystub | — | — | gap | |
| permits | permit | — | <https://schema.org/Permit> | exact | |
| plans | plan | — | — | gap | |
| policies | policy | — | — | gap | Insurance policies; no clean external authority. |
| portfolios | portfolio | — | — | gap | |
| presentations | presentation | — | — | gap | Deferred straddler. |
| quotes | quote | — | — | gap | |
| receipts | receipt | — | <https://schema.org/Order> ("a confirmation of a transaction (a receipt)") | exact | `order` aliases here. |
| recipes | recipe | — | <https://schema.org/Recipe> (CreativeWork > HowTo > Recipe) | exact | |
| records | record | LCGFT gf2014026163 (Records (Documents)) | — | broader | LCGFT parent of legal instruments and similar. |
| references | reference | LCGFT "Reference works" (under Informational works) | — | broader | |
| referrals | referral | — | — | gap | |
| reports | report | — | <https://schema.org/Report> (CreativeWork > Article > Report) | exact | |
| reservations | reservation | — | <https://schema.org/Reservation> (9 subtypes) | exact | All 9 subtypes accepted via aliases. |
| resumes | resume | — | — | gap | |
| returns | return | — | — | gap | Tax returns. |
| statements | statement | — | — | gap | Documented gap. |
| titles | title | — | — | gap | Vehicle titles, deeds of title. |
| trusts | trust | — | — | gap | Trust instruments. |
| warranties | warranty | — | — | gap | |
| wills | will | — | — | gap | |

## schema.org Reservation subtypes routed via DOCTYPE_ALIASES

All 9 subtypes from <https://schema.org/Reservation> normalize to
canonical `reservations` via `DOCTYPE_ALIASES`:

- BoatReservation
- BusReservation
- EventReservation
- FlightReservation
- FoodEstablishmentReservation
- LodgingReservation
- RentalCarReservation
- ReservationPackage
- TaxiReservation
- TrainReservation

This keeps Drover's flat doctype axis (no subtypes inside the axis) while
accepting schema.org-flavored emissions from contributors using
schema.org-trained models.

## schema.org transactional aliases

| schema.org term | Drover doctype | Reasoning |
|---|---|---|
| Order | receipts | "a confirmation of a transaction (a receipt)" per schema.org. |
| Ticket | reservations | Tickets carry timing/availability semantics; route to reservations rather than expand the axis. |

## Folder vs filename

Drover folders use the **plural** canonical doctype (LCGFT genre alignment:
"Receipts is the genre, this folder holds many receipt instances"). Filenames
use the **singular** instance form ("this one file is one receipt"). The
mapping lives in `HouseholdTaxonomy.DOCTYPE_SINGULAR`; `PathBuilder` calls
`taxonomy.singular_form()` before passing the doctype to the naming policy.

## Extending

When proposing a new doctype:

1. Check LCGFT first (form authority).
2. Check schema.org for transactional/web-entity counterparts.
3. If neither commits, document the gap in this table rather than inventing a
   private term.
4. Confirm corpus signal before promotion (Drover's evidence-first precedent;
   see `docs/taxonomy/proposals.md`).
