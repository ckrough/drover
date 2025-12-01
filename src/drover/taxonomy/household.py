"""Household taxonomy for homeowner document classification.

A comprehensive taxonomy covering typical household document categories
including financial, property, medical, legal, and personal documents.
"""

from typing import ClassVar

from drover.taxonomy.base import BaseTaxonomy


class HouseholdTaxonomy(BaseTaxonomy):
    """Default taxonomy for household/homeowner documents."""

    CANONICAL_DOMAINS: ClassVar[set[str]] = {
        "financial",
        "property",
        "medical",
        "legal",
        "employment",
        "education",
        "insurance",
        "vehicles",
        "personal",
        "government",
        "utilities",
        "other",
    }

    CANONICAL_CATEGORIES: ClassVar[dict[str, set[str]]] = {
        "financial": {
            "banking",
            "credit",
            "investments",
            "retirement",
            "taxes",
            "loans",
            "other",
        },
        "property": {
            "purchase",
            "mortgage",
            "maintenance",
            "improvements",
            "hoa",
            "rental",
            "other",
        },
        "medical": {
            "records",
            "billing",
            "insurance_claims",
            "prescriptions",
            "lab_results",
            "other",
        },
        "legal": {
            "contracts",
            "estate_planning",
            "court",
            "correspondence",
            "other",
        },
        "employment": {
            "compensation",
            "benefits",
            "performance",
            "correspondence",
            "other",
        },
        "education": {
            "transcripts",
            "certifications",
            "correspondence",
            "financial_aid",
            "other",
        },
        "insurance": {
            "auto",
            "home",
            "life",
            "health",
            "umbrella",
            "claims",
            "other",
        },
        "vehicles": {
            "purchase",
            "registration",
            "maintenance",
            "insurance",
            "loans",
            "other",
        },
        "personal": {
            "identity",
            "correspondence",
            "memberships",
            "travel",
            "other",
        },
        "government": {
            "federal",
            "state",
            "local",
            "correspondence",
            "other",
        },
        "utilities": {
            "electric",
            "gas",
            "water",
            "internet",
            "phone",
            "trash",
            "other",
        },
        "other": {
            "uncategorized",
        },
    }

    CANONICAL_DOCTYPES: ClassVar[set[str]] = {
        "statement",
        "invoice",
        "receipt",
        "contract",
        "agreement",
        "letter",
        "notice",
        "form",
        "application",
        "policy",
        "certificate",
        "report",
        "record",
        "bill",
        "estimate",
        "quote",
        "warranty",
        "manual",
        "guide",
        "tax_return",
        "tax_form",
        "deed",
        "title",
        "license",
        "permit",
        "other",
    }

    # Common variations → canonical domain
    DOMAIN_ALIASES: ClassVar[dict[str, str]] = {
        "finances": "financial",
        "finance": "financial",
        "money": "financial",
        "banking": "financial",
        "home": "property",
        "house": "property",
        "real_estate": "property",
        "realestate": "property",
        "health": "medical",
        "healthcare": "medical",
        "doctor": "medical",
        "hospital": "medical",
        "law": "legal",
        "attorney": "legal",
        "lawyer": "legal",
        "work": "employment",
        "job": "employment",
        "career": "employment",
        "school": "education",
        "college": "education",
        "university": "education",
        "car": "vehicles",
        "auto": "vehicles",
        "automobile": "vehicles",
        "truck": "vehicles",
        "gov": "government",
        "govt": "government",
        "federal": "government",
        "state": "government",
        "bills": "utilities",
        "misc": "other",
        "miscellaneous": "other",
        "unknown": "other",
    }

    # (domain, variation) → canonical category
    CATEGORY_ALIASES: ClassVar[dict[tuple[str, str], str]] = {
        # Financial
        ("financial", "bank"): "banking",
        ("financial", "checking"): "banking",
        ("financial", "savings"): "banking",
        ("financial", "credit_card"): "credit",
        ("financial", "credit_cards"): "credit",
        ("financial", "cards"): "credit",
        ("financial", "stocks"): "investments",
        ("financial", "bonds"): "investments",
        ("financial", "brokerage"): "investments",
        ("financial", "401k"): "retirement",
        ("financial", "ira"): "retirement",
        ("financial", "pension"): "retirement",
        ("financial", "tax"): "taxes",
        ("financial", "irs"): "taxes",
        # Property
        ("property", "home_improvement"): "improvements",
        ("property", "home_improvements"): "improvements",
        ("property", "repairs"): "maintenance",
        ("property", "home_repairs"): "maintenance",
        ("property", "association"): "hoa",
        ("property", "condo"): "hoa",
        # Medical
        ("medical", "health_records"): "records",
        ("medical", "medical_records"): "records",
        ("medical", "bills"): "billing",
        ("medical", "claims"): "insurance_claims",
        ("medical", "rx"): "prescriptions",
        ("medical", "medications"): "prescriptions",
        ("medical", "labs"): "lab_results",
        ("medical", "tests"): "lab_results",
        # Insurance
        ("insurance", "car"): "auto",
        ("insurance", "vehicle"): "auto",
        ("insurance", "homeowners"): "home",
        ("insurance", "property"): "home",
        ("insurance", "medical"): "health",
    }

    # variation → canonical doctype
    DOCTYPE_ALIASES: ClassVar[dict[str, str]] = {
        "bank_statement": "statement",
        "account_statement": "statement",
        "monthly_statement": "statement",
        "bill": "invoice",
        "payment": "receipt",
        "purchase": "receipt",
        "transaction": "receipt",
        "lease": "agreement",
        "rental_agreement": "agreement",
        "service_agreement": "agreement",
        "correspondence": "letter",
        "mail": "letter",
        "notification": "notice",
        "alert": "notice",
        "reminder": "notice",
        "document": "form",
        "paperwork": "form",
        "insurance_policy": "policy",
        "coverage": "policy",
        "cert": "certificate",
        "certification": "certificate",
        "credential": "certificate",
        "assessment": "report",
        "summary": "report",
        "analysis": "report",
        "history": "record",
        "log": "record",
        "proposal": "estimate",
        "bid": "quote",
        "owner_manual": "manual",
        "instructions": "guide",
        "how_to": "guide",
        "1040": "tax_return",
        "w2": "tax_form",
        "w-2": "tax_form",
        "1099": "tax_form",
        "property_deed": "deed",
        "car_title": "title",
        "vehicle_title": "title",
        "drivers_license": "license",
        "registration": "license",
        "unknown": "other",
    }

    @property
    def name(self) -> str:
        """Unique identifier for this taxonomy."""
        return "household"
