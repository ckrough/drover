"""Household taxonomy for homeowner document classification.

A comprehensive taxonomy covering typical household document categories
including financial, property, medical, legal, and personal documents.

Authority alignment (Round 4):
- Doctypes are LCGFT-style genre/form containers (folder layer); filenames
  use the singular instance form. See ``DOCTYPE_SINGULAR``.
- LCGFT (Library of Congress Genre/Form Terms) authority for doctype labels.
- schema.org for transactional and web-entity aliases.

Detailed cross-references live in ``docs/taxonomy/external-mapping.md``.
The form-vs-subject design rationale (LCGFT alignment) lives in
``docs/taxonomy/design-rationale.md``.
"""

from typing import ClassVar

from drover.taxonomy.base import BaseTaxonomy


class HouseholdTaxonomy(BaseTaxonomy):
    """Default taxonomy for household/homeowner documents."""

    CANONICAL_DOMAINS: ClassVar[set[str]] = {
        "career",
        "education",
        "financial",
        "food",
        "government",
        "household",
        "housing",
        "insurance",
        "legal",
        "lifestyle",
        "medical",
        "personal",
        "pets",
        "property",
        "reference",
        "utilities",
    }

    CANONICAL_CATEGORIES: ClassVar[dict[str, set[str]]] = {
        "financial": {
            "banking",
            "credit",
            "investment",
            "loan",
            "payment",
            "retirement",
            "tax",
        },
        "property": {
            "expense",
            "hoa",
            "improvement",
            "maintenance",
            "mortgage",
            "payment",
            "rental",
            "search",
        },
        "medical": {
            "claim",
            "expense",
            "immunization",
            "lab_result",
            "mental_health",
            "payment",
            "prescription",
            "primary_care",
            "specialist",
            "vision",
        },
        # Round 4: `contract` removed from legal categories. LCGFT has no
        # standalone Contracts term; specific instrument doctypes (agreements,
        # deeds, leases, titles, trusts, wills) carry the load. The fuller
        # LCGFT Law-materials restructure (instruments, claims, court_records,
        # statutes) is deferred until corpus signal supports it (Drover's
        # evidence-first precedent).
        "legal": {
            "court",
            "estate",
        },
        "education": {
            "certification",
            "expense",
            "financial_aid",
            "payment",
            "transcript",
        },
        "insurance": {
            "auto",
            "claim",
            "health",
            "home",
            "life",
            "payment",
            "umbrella",
        },
        "personal": {
            "expense",
            "identity",
            "membership",
            "travel",
        },
        "government": {
            "federal",
            "local",
            "state",
        },
        "utilities": {
            "electric",
            "expense",
            "gas",
            "internet",
            "payment",
            "phone",
            "trash",
            "water",
        },
        "career": {
            "application",
            "benefit",
            "client",
            "compensation",
            "consulting",
            "documentation",
            "employer",
            "expense",
            "job_search",
            "leadership",
            "meeting",
            "presentation",
            "review",
            "training",
        },
        # Round 4: `recipe` demoted from food categories. Schema.org Recipe is
        # a CreativeWork (HowTo subtype); the doctype `recipes` carries the
        # form. Food-domain recipe artifacts surface as drift for ground-truth
        # refinement.
        "food": {
            "meal_plan",
        },
        "household": {
            "documentation",
            "expense",
            "goods",
            "network",
            "insurance",
            "loans",
            "maintenance",
            "purchase",
            "registration",
            "vehicle",
        },
        "lifestyle": {
            "expense",
            "goal",
            "interest",
            "planning",
            "travel",
            "volunteering",
        },
        "pets": {
            "expense",
            "medical",
            "registration",
        },
        "reference": {
            "documentation",
            "topic",
        },
        # Round 4: `reservation` demoted from housing categories. Schema.org
        # Reservation is Intangible/transactional; the doctype `reservations`
        # carries the form (with 9 schema.org subtype aliases below).
        "housing": {
            "payment",
            "property",
            "rental",
            "search",
        },
    }

    # Doctype axis = LCGFT-style genre/form containers (folder labels).
    # Each holds individual instances; filenames use the singular form
    # via DOCTYPE_SINGULAR. See docs/taxonomy/external-mapping.md for the
    # full LCGFT/schema.org cross-reference.
    CANONICAL_DOCTYPES: ClassVar[set[str]] = {
        "agreements",  # LCGFT Legal instruments (under Records (Documents))
        "applications",  # deferred straddler — no authority commits
        "bills",  # no authority; aliased pattern with invoices
        "certificates",  # schema.org/Certification
        "confirmations",  # documented gap; no clean external authority
        "deeds",  # LCGFT subject heading
        "estimates",
        "floor_plans",  # LCGFT Floor plans (under Informational works)
        "forms",  # LCGFT Blank forms
        "guides",  # LCGFT gf2014026108 (Guidebooks)
        "identifications",
        "invoices",  # schema.org/Invoice (Intangible)
        "itineraries",
        "journals",  # LCGFT gf2014026085 (Diaries)
        "leases",
        "letters",  # LCGFT gf2014026141 (Personal correspondence)
        "licenses",
        "listings",  # schema.org/RealEstateListing
        "manuals",  # LCGFT gf2014026109 (Handbooks and manuals)
        "maps",  # LCGFT gf2011026387; schema.org/Map
        "menus",  # LCGFT Menus; schema.org/Menu
        "notices",  # adversarial/regulatory connotation; distinct from letters
        "offers",  # documented gap; schema.org/Offer is price/availability
        "passports",
        "paystubs",
        "permits",  # schema.org/Permit
        "plans",
        "policies",  # insurance — no clean external authority
        "portfolios",
        "presentations",  # deferred straddler
        "quotes",
        "receipts",  # schema.org/Order ("confirmation of a transaction (a receipt)")
        "recipes",  # schema.org/Recipe (CreativeWork > HowTo > Recipe)
        "records",  # LCGFT gf2014026163 (Records (Documents))
        "references",  # LCGFT Reference works (under Informational works)
        "referrals",
        "reports",  # schema.org/Report (CreativeWork > Article > Report)
        "reservations",  # schema.org/Reservation (9 subtypes accepted via aliases)
        "resumes",
        "returns",  # tax returns
        "statements",  # documented gap; no clean external authority
        "titles",
        "trusts",
        "warranties",
        "wills",
    }

    # Plural canonical -> singular instance form for filename use.
    # NARAPolicyNaming.format_filename() consults this so folders stay plural
    # (LCGFT genre alignment) and filenames read as one-instance artifacts.
    DOCTYPE_SINGULAR: ClassVar[dict[str, str]] = {
        "agreements": "agreement",
        "applications": "application",
        "bills": "bill",
        "certificates": "certificate",
        "confirmations": "confirmation",
        "deeds": "deed",
        "estimates": "estimate",
        "floor_plans": "floor_plan",
        "forms": "form",
        "guides": "guide",
        "identifications": "identification",
        "invoices": "invoice",
        "itineraries": "itinerary",
        "journals": "journal",
        "leases": "lease",
        "letters": "letter",
        "licenses": "license",
        "listings": "listing",
        "manuals": "manual",
        "maps": "map",
        "menus": "menu",
        "notices": "notice",
        "offers": "offer",
        "passports": "passport",
        "paystubs": "paystub",
        "permits": "permit",
        "plans": "plan",
        "policies": "policy",
        "portfolios": "portfolio",
        "presentations": "presentation",
        "quotes": "quote",
        "receipts": "receipt",
        "recipes": "recipe",
        "records": "record",
        "references": "reference",
        "referrals": "referral",
        "reports": "report",
        "reservations": "reservation",
        "resumes": "resume",
        "returns": "return",
        "statements": "statement",
        "titles": "title",
        "trusts": "trust",
        "warranties": "warranty",
        "wills": "will",
    }

    DOMAIN_ALIASES: ClassVar[dict[str, str]] = {
        "apartment": "housing",
        "attorney": "legal",
        "auto": "household",
        "automobile": "household",
        "banking": "financial",
        "bills": "utilities",
        "car": "household",
        "college": "education",
        "doctor": "medical",
        "federal": "government",
        "finance": "financial",
        "finances": "financial",
        "gov": "government",
        "govt": "government",
        "health": "medical",
        "healthcare": "medical",
        "home": "property",
        "hospital": "medical",
        "house": "property",
        "job": "career",
        "law": "legal",
        "lawyer": "legal",
        "lease": "housing",
        "money": "financial",
        "real_estate": "housing",
        "realestate": "housing",
        "rental": "housing",
        "rentals": "housing",
        "school": "education",
        "state": "government",
        "travel": "lifestyle",
        "truck": "household",
        "university": "education",
        "vehicle": "household",
        "vehicles": "household",
        "work": "career",
        "non_profit": "personal",
        "nonprofit": "personal",
    }

    CATEGORY_ALIASES: ClassVar[dict[tuple[str, str], str]] = {
        ("career", "interviewing"): "job_search",
        ("career", "docs"): "documentation",
        # Hierarchy rule: artifact-form terms (resume, manual, agreement, ...)
        # are doctype-only. These aliases redirect LLM-emitted forms to the
        # appropriate subject category in each domain. Domains without an
        # entry below deliberately surface the term as drift (canonical: null)
        # for ground-truth refinement.
        ("career", "resume"): "job_search",
        ("reference", "manual"): "documentation",
        ("property", "agreement"): "mortgage",
        ("housing", "agreement"): "rental",
        ("personal", "goals"): "identity",
        ("financial", "bank"): "banking",
        ("financial", "checking"): "banking",
        ("financial", "savings"): "banking",
        ("financial", "credit_card"): "credit",
        ("financial", "credit_cards"): "credit",
        ("financial", "cards"): "credit",
        ("financial", "stocks"): "investment",
        ("financial", "bonds"): "investment",
        ("financial", "brokerage"): "investment",
        ("financial", "equities"): "investment",
        ("financial", "401k"): "retirement",
        ("financial", "ira"): "retirement",
        ("financial", "pension"): "retirement",
        ("financial", "taxes"): "tax",
        ("financial", "irs"): "tax",
        ("financial", "account"): "banking",
        ("financial", "account_information"): "banking",
        ("financial", "account_statement"): "banking",
        ("financial", "accounting"): "banking",
        ("financial", "statement"): "banking",
        ("financial", "transaction"): "banking",
        ("financial", "transfer"): "banking",
        ("financial", "transfer_money"): "banking",
        ("financial", "credit_card_statement"): "credit",
        ("financial", "distribution"): "retirement",
        ("financial", "loan_documents"): "loan",
        ("financial", "payment_services"): "payment",
        # property domain
        ("property", "home_improvement"): "improvement",
        ("property", "home_improvements"): "improvement",
        ("property", "repairs"): "maintenance",
        ("property", "home_repairs"): "maintenance",
        ("property", "association"): "hoa",
        ("property", "condo"): "hoa",
        ("property", "lease"): "rental",
        ("property", "housing"): "rental",
        ("property", "termination_of_service"): "maintenance",
        ("property", "receipts"): "expense",
        ("property", "purchases"): "expense",
        ("property", "spending"): "expense",
        # medical domain
        ("medical", "bills"): "expense",
        ("medical", "claims"): "claim",
        ("medical", "rx"): "prescription",
        ("medical", "medications"): "prescription",
        ("medical", "labs"): "lab_result",
        ("medical", "tests"): "lab_result",
        ("medical", "annual_examination"): "primary_care",
        ("medical", "exam"): "primary_care",
        ("medical", "visit"): "primary_care",
        ("medical", "behavior_modification"): "mental_health",
        # insurance domain
        ("insurance", "car"): "auto",
        ("insurance", "vehicle"): "auto",
        ("insurance", "homeowners"): "home",
        ("insurance", "property"): "home",
        ("insurance", "medical"): "health",
        # housing domain
        ("housing", "apartment"): "rental",
        ("housing", "lease"): "rental",
        ("housing", "real_estate"): "property",
        ("housing", "mortgage"): "property",
        ("housing", "home"): "property",
        # lifestyle domain
        ("lifestyle", "trip"): "travel",
        ("lifestyle", "vacation"): "travel",
        ("lifestyle", "trips"): "travel",
        ("lifestyle", "trip_itinerary"): "travel",
        ("lifestyle", "travel_planning"): "planning",
        ("lifestyle", "receipts"): "expense",
        ("lifestyle", "purchases"): "expense",
        ("lifestyle", "spending"): "expense",
        # pets domain
        ("pets", "receipts"): "expense",
        ("pets", "purchases"): "expense",
        ("pets", "spending"): "expense",
        # household domain
        ("household", "receipts"): "expense",
        ("household", "purchases"): "expense",
        ("household", "spending"): "expense",
        ("household", "vehicle_registration_renewal"): "registration",
        ("household", "vehicle_related_policies"): "insurance",
        # career domain
        ("career", "receipts"): "expense",
        ("career", "purchases"): "expense",
        ("career", "spending"): "expense",
        ("career", "billing"): "compensation",
        # financial domain - additional aliases
        ("financial", "billing"): "payment",
        ("financial", "compensation"): "payment",
        ("financial", "correspondence"): "banking",
        # lifestyle domain - career-related aliases
        ("lifestyle", "career"): "planning",
        ("lifestyle", "job_search"): "planning",
        ("lifestyle", "training"): "interest",
        ("lifestyle", "volunteer_programming"): "volunteering",
        # personal domain - non-profit aliases (when non_profit maps to personal)
        ("personal", "annual_report"): "membership",
        # household domain - vehicles aliases (when vehicles maps to household)
        ("household", "vehicle_service_records"): "vehicle",
        # education domain
        ("education", "receipts"): "expense",
        ("education", "purchases"): "expense",
        ("education", "spending"): "expense",
        ("education", "tuition"): "expense",
        # singular `purchase` (LLM emits singular alongside plural)
        ("food", "purchase"): "expense",
        ("property", "purchase"): "expense",
        ("personal", "purchase"): "expense",
        ("lifestyle", "purchase"): "expense",
        ("career", "purchase"): "expense",
        # gerund variants of `travel`
        ("personal", "traveling"): "travel",
        ("lifestyle", "traveling"): "travel",
        # `billing` is what the LLM calls a payment notice
        ("insurance", "billing"): "payment",
        ("medical", "billing"): "payment",
        # one-off but unambiguous
        ("lifestyle", "gift_giving"): "expense",
    }

    DOCTYPE_ALIASES: ClassVar[dict[str, str]] = {
        # --- Singular -> plural (LLM emission normalization) ---
        # Models trained on individual-document language emit the singular
        # ("receipt", "invoice"); we route to the plural folder/genre form.
        "agreement": "agreements",
        "application": "applications",
        "bill": "bills",
        "certificate": "certificates",
        "confirmation": "confirmations",
        "deed": "deeds",
        "estimate": "estimates",
        "floor_plan": "floor_plans",
        "form": "forms",
        "guide": "guides",
        "identification": "identifications",
        "invoice": "invoices",
        "itinerary": "itineraries",
        "journal": "journals",
        "lease": "leases",
        "letter": "letters",
        "license": "licenses",
        "listing": "listings",
        "manual": "manuals",
        "map": "maps",
        "menu": "menus",
        "notice": "notices",
        "offer": "offers",
        "passport": "passports",
        "paystub": "paystubs",
        "permit": "permits",
        "plan": "plans",
        "policy": "policies",
        "portfolio": "portfolios",
        "presentation": "presentations",
        "quote": "quotes",
        "receipt": "receipts",
        "recipe": "recipes",
        "record": "records",
        "reference": "references",
        "referral": "referrals",
        "report": "reports",
        "reservation": "reservations",
        "resume": "resumes",
        "return": "returns",
        "statement": "statements",
        "title": "titles",
        "trust": "trusts",
        "warranty": "warranties",
        "will": "wills",
        # --- schema.org Reservation subtypes ---
        # https://schema.org/Reservation has 9 subtypes; route each to the
        # plural reservations container so schema.org-trained emissions land
        # without expanding the doctype axis.
        "boat_reservation": "reservations",
        "bus_reservation": "reservations",
        "event_reservation": "reservations",
        "flight_reservation": "reservations",
        "food_establishment_reservation": "reservations",
        "lodging_reservation": "reservations",
        "rental_car_reservation": "reservations",
        "reservation_package": "reservations",
        "taxi_reservation": "reservations",
        "train_reservation": "reservations",
        # --- schema.org transactional types ---
        # Order = "a confirmation of a transaction (a receipt)" per schema.org.
        "order": "receipts",
        "ticket": "reservations",
        "tickets": "reservations",
        # Round 4: legacy `contract` doctype dropped; route to the closest
        # LCGFT-aligned legal-instrument container for backwards compatibility
        # with prior LLM emissions.
        "contract": "agreements",
        "contracts": "agreements",
        # --- LCGFT-derived synonyms ---
        # Plural-target aliases for prior singular-routed synonyms.
        "bank_statement": "statements",
        "account_statement": "statements",
        "monthly_statement": "statements",
        "service_agreement": "agreements",
        "correspondence": "letters",
        "mail": "letters",
        "notification": "notices",
        "alert": "notices",
        "reminder": "notices",
        "document": "forms",
        "paperwork": "forms",
        "insurance_policy": "policies",
        "coverage": "policies",
        "cert": "certificates",
        "certification": "certificates",
        "credential": "certificates",
        "assessment": "reports",
        "summary": "reports",
        "analysis": "reports",
        "history": "records",
        "log": "records",
        "proposal": "estimates",
        "bid": "quotes",
        "owner_manual": "manuals",
        "instructions": "guides",
        "how_to": "guides",
        "1040": "returns",
        "w2": "forms",
        "w-2": "forms",
        "1099": "forms",
        "property_deed": "deeds",
        "car_title": "titles",
        "vehicle_title": "titles",
        "drivers_license": "licenses",
        "registration": "licenses",
        "cookbook": "recipes",
        "cv": "resumes",
        "shot_record": "records",
        "travel_plan": "itineraries",
        # paystub aliases
        "pay_stub": "paystubs",
        "paycheck": "paystubs",
        "earnings_statement": "paystubs",
        # lease aliases
        "rental_agreement": "leases",
        "apartment_lease": "leases",
        "rental_lease": "leases",
        # listing aliases
        "property_listing": "listings",
        "mls_listing": "listings",
        "real_estate_listing": "listings",
        # offer aliases
        "purchase_offer": "offers",
        "real_estate_offer": "offers",
        # closing aliases
        "closing_docs": "statements",
        "settlement_statement": "statements",
        "hud1": "statements",
        # hoa aliases
        "hoa_dues": "statements",
        "hoa_bill": "statements",
        # --- Empirically discovered (eval drift) ---
        "billing_statement": "statements",
        "claim_confirmation": "confirmations",
        "insurance": "policies",
        "lease_agreement": "leases",
        "mortgage": "agreements",
        "pay_bill": "receipts",
        "payment": "receipts",
        "payment_confirmation": "confirmations",
        "payment_receipt": "receipts",
        "payment_scheduled": "confirmations",
        "purchase": "receipts",
        "transaction": "receipts",
        "request_for_termination_of_service": "notices",
        "transfer_money_confirmation": "confirmations",
        # discovered aliases - job search and reference
        "article": "references",
        "call_notes": "records",
        "job_listing": "listings",
        "job_posting": "listings",
        # discovered aliases - healthcare
        "list": "references",
        "medical_billing_statement": "statements",
        "patient_care_summary": "reports",
        # discovered aliases - lifestyle
        "discharge_summary": "reports",
        "service_record": "records",
        "webpage": "references",
    }

    @property
    def name(self) -> str:
        """Unique identifier for this taxonomy."""
        return "household"
