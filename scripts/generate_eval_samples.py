#!/usr/bin/env python3
"""Synthetic eval-corpus generator for drover NLI accuracy baselines.

Picks (domain, category, doctype) triples from HouseholdTaxonomy, asks
Claude to write realistic prose for each, renders the result as a PDF,
and appends a row to eval/ground_truth.jsonl.

Usage:
    uv run python scripts/generate_eval_samples.py --dry-run
    uv run python scripts/generate_eval_samples.py --count 3 --ai-model claude-haiku-4-5-20251001 \\
        --output-dir eval/samples-smoke --ground-truth eval/ground_truth_smoke.jsonl
    uv run python scripts/generate_eval_samples.py --count 30 --concurrency 5
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import re
import sys
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, NamedTuple

import click
from pydantic import BaseModel, ValidationError, field_validator

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from drover.config import LogLevel
from drover.logging import configure_logging, get_logger
from drover.taxonomy.loader import get_taxonomy

if TYPE_CHECKING:
    from langchain_anthropic import ChatAnthropic
    from transformers import PreTrainedTokenizerBase  # type: ignore[import-not-found]

    from drover.taxonomy.base import BaseTaxonomy

logger = get_logger(__name__)

# -- Constants ----------------------------------------------------------------

NLI_TOKENIZER_ID = "cross-encoder/nli-deberta-v3-base"
LONG_DOC_THRESHOLD = 512

# Per-million-token pricing (USD). Update if Anthropic changes rates.
MODEL_PRICING: dict[str, dict[str, float]] = {
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_write": 3.75,
        "cache_read": 0.30,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.00,
        "output": 5.00,
        "cache_write": 1.25,
        "cache_read": 0.10,
    },
}

# Triples picked for naturally verbose docs (used to fill --min-long-docs).
LONG_TRIPLES: list[tuple[str, str, str]] = [
    ("housing", "rental", "lease"),
    ("legal", "contract", "contract"),
    ("legal", "estate", "will"),
    ("insurance", "auto", "policy"),
    ("insurance", "home", "policy"),
    ("financial", "investment", "statement"),
    ("financial", "tax", "return"),
    ("property", "agreement", "agreement"),
    ("household", "documentation", "manual"),
    ("reference", "manual", "manual"),
    ("government", "federal", "form"),
    ("education", "agreement", "agreement"),
]

# At least one default short triple per domain. The coverage planner extends
# this with extra picks until --count is hit.
DOMAIN_DEFAULT_TRIPLE: dict[str, tuple[str, str, str]] = {
    "career": ("career", "employer", "paystub"),
    "education": ("education", "transcript", "report"),
    "financial": ("financial", "banking", "statement"),
    "food": ("food", "recipe", "recipe"),
    "government": ("government", "correspondence", "letter"),
    "household": ("household", "expense", "receipt"),
    "housing": ("housing", "rental", "lease"),
    "insurance": ("insurance", "auto", "policy"),
    "legal": ("legal", "correspondence", "letter"),
    "lifestyle": ("lifestyle", "travel", "itinerary"),
    "medical": ("medical", "expense", "invoice"),
    "personal": ("personal", "membership", "certificate"),
    "pets": ("pets", "expense", "receipt"),
    "property": ("property", "expense", "receipt"),
    "reference": ("reference", "manual", "manual"),
    "utilities": ("utilities", "electric", "invoice"),
}

# Per-domain vendor pools. Synthetic; no real organizations.
VENDOR_POOLS: dict[str, list[str]] = {
    "career": [
        "Stratford Consulting",
        "Meridian Software",
        "Apex Labs",
        "Northwind Studios",
    ],
    "education": ["Lakeside University", "Hillcrest College", "Summit Academy"],
    "financial": [
        "Northern Capital Bank",
        "Heritage Trust",
        "Crestline Federal Credit Union",
    ],
    "food": ["Willowbrook Market", "Harvest Table Co-op", "Maple Lane Grocers"],
    "government": [
        "Department of Public Records",
        "State Tax Authority",
        "County Permits Office",
    ],
    "household": ["Brightway Hardware", "Cedar & Pine Home", "Ironwood Supply"],
    "housing": ["Bayside Property Management", "Oakridge Realty", "Westhaven Rentals"],
    "insurance": ["Allport Insurance Group", "Sentinel Mutual", "Keystone Coverage"],
    "legal": ["Marlowe & Stone LLP", "Hartwell Legal Services", "Brightford Notary"],
    "lifestyle": ["Wayfarer Travel", "Greenleaf Tours", "Coastline Adventures"],
    "medical": [
        "Riverbend Medical Center",
        "Greenwood Family Practice",
        "Northgate Dental",
    ],
    "personal": [
        "Civic Library Association",
        "Lighthouse Volunteers",
        "Harbor Athletic Club",
    ],
    "pets": ["Furry Friends Veterinary", "Pawsworth Supply", "Wagging Tails Boarding"],
    "property": ["Highland HOA", "Riverstone Maintenance", "Sterling Property Group"],
    "reference": ["Open Knowledge Press", "Bluefield Reference Library"],
    "utilities": ["Cascade Power", "Summit Water District", "Bridgeport Telecom"],
}

# Per-domain plausible doctypes. The coverage planner restricts the random
# fill to these triples (the global CANONICAL_DOCTYPES set is too broad and
# generates nonsense like "household/registration/paystub").
DOMAIN_DOCTYPES: dict[str, set[str]] = {
    "career": {"resume", "paystub", "letter", "report", "certificate", "agreement"},
    "education": {"report", "letter", "certificate", "agreement", "invoice", "receipt"},
    "financial": {"statement", "receipt", "invoice", "return", "letter", "report"},
    "food": {"recipe", "receipt", "guide", "manual"},
    "government": {"letter", "form", "notice", "certificate", "license", "permit"},
    "household": {"receipt", "manual", "warranty", "invoice", "guide", "policy"},
    "housing": {"lease", "listing", "offer", "agreement", "letter", "notice"},
    "insurance": {"policy", "statement", "letter", "notice", "form", "invoice"},
    "legal": {"contract", "letter", "will", "trust", "agreement", "form"},
    "lifestyle": {"itinerary", "receipt", "reservation", "confirmation", "plan"},
    "medical": {"invoice", "statement", "report", "record", "letter", "referral"},
    "personal": {"certificate", "letter", "passport", "identification", "license"},
    "pets": {"receipt", "record", "invoice", "agreement", "certificate"},
    "property": {"receipt", "deed", "estimate", "invoice", "report", "agreement"},
    "reference": {"manual", "guide", "reference"},
    "utilities": {"invoice", "statement", "notice", "letter", "agreement"},
}

# Domain-aware amount ranges (USD, integer dollars).
AMOUNT_RANGES: dict[str, tuple[int, int]] = {
    "career": (1500, 9000),
    "education": (200, 8000),
    "financial": (50, 25000),
    "food": (20, 250),
    "government": (15, 500),
    "household": (10, 600),
    "housing": (1200, 4500),
    "insurance": (300, 3500),
    "legal": (250, 6000),
    "lifestyle": (100, 4000),
    "medical": (50, 5000),
    "personal": (10, 300),
    "pets": (15, 800),
    "property": (50, 2500),
    "reference": (0, 50),
    "utilities": (30, 400),
}

INJECTION_MARKERS: tuple[str, ...] = (
    "ignore previous",
    "ignore the previous",
    "system:",
    "assistant:",
    "<|im_start|>",
    "<|im_end|>",
    "<|endoftext|>",
)


# -- Data classes -------------------------------------------------------------


class Triple(NamedTuple):
    """A (domain, category, doctype) classification target."""

    domain: str
    category: str
    doctype: str


class GroundTruthRow(BaseModel):
    """One JSONL row in eval/ground_truth.jsonl (validated against taxonomy)."""

    filename: str
    domain: str
    category: str
    doctype: str
    vendor: str
    date: str
    subject: str
    notes: str = ""

    @field_validator("date")
    @classmethod
    def _validate_date(cls, v: str) -> str:
        if v == "00000000":
            return v
        if not re.fullmatch(r"\d{8}", v):
            raise ValueError(f"date must be YYYYMMDD or '00000000', got {v!r}")
        if "0000" in (v[:4], v[4:6], v[6:8]):
            raise ValueError(f"partial-zero dates are forbidden, got {v!r}")
        return v


class GenerationResult(BaseModel):
    """Outcome of one generation attempt."""

    triple: Triple
    text: str
    pdf_path: Path
    row: GroundTruthRow
    token_count: int
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    model: str

    model_config = {"arbitrary_types_allowed": True}


# -- Helpers ------------------------------------------------------------------


def _slugify(text: str) -> str:
    """Lowercase, hyphenated, alphanumeric-only slug."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or "unknown"


def _filename(triple: Triple, vendor: str, doc_date: date) -> str:
    """Build {vendor-slug}_{doctype}_{yyyy-mm-dd}.pdf, ≤50 chars."""
    vendor_slug = _slugify(vendor)
    iso = doc_date.isoformat()
    base = f"{vendor_slug}_{triple.doctype}_{iso}.pdf"
    if len(base) > 50:
        max_vendor = 50 - len(f"_{triple.doctype}_{iso}.pdf")
        vendor_slug = vendor_slug[:max_vendor].rstrip("-")
        base = f"{vendor_slug}_{triple.doctype}_{iso}.pdf"
    return base


# Per-doctype structural guidance. The renderer parses markdown headings,
# bullet/numbered lists, pipe tables, and horizontal rules into reportlab
# elements, so prompts that ask for those constructs get rendered with real
# document structure (not just memo-style prose).
DOCTYPE_STRUCTURE_HINTS: dict[str, str] = {
    "invoice": (
        "Format as a real invoice. Begin with a vendor address block (company "
        "name, street, city, state, ZIP) on separate lines, then 'INVOICE' as a "
        "# heading, an invoice number and date line, and a customer 'Bill To:' "
        "block. Include a markdown table of line items with columns "
        "'Description | Qty | Unit Price | Total'. End with subtotal/tax/total "
        "rows in a small markdown table, then payment terms."
    ),
    "receipt": (
        "Format as a real point-of-sale receipt. Begin with the vendor name "
        "centered (use # heading), address, and phone. Include a date/time and "
        "transaction ID line, then a markdown table of items with "
        "'Item | Qty | Price' columns. End with subtotal, tax, total rows and a "
        "'Thank you' closing line."
    ),
    "statement": (
        "Format as a real account statement. Begin with the institution name "
        "and address, account holder block, statement period, and account "
        "number. Include a markdown table of activity with "
        "'Date | Description | Amount | Balance' columns (5-10 rows). End with "
        "a summary section listing opening balance, total deposits, total "
        "withdrawals, and closing balance."
    ),
    "bill": (
        "Format as a real utility/service bill. Begin with provider name and "
        "address, customer account block, billing period. Include a markdown "
        "table of charges with 'Description | Amount' columns. End with a "
        "summary box noting amount due, due date, and how to pay."
    ),
    "paystub": (
        "Format as a real pay stub. Begin with employer name and address, then "
        "an employee block (name, employee ID, pay period). Include TWO "
        "markdown tables: (1) earnings 'Description | Hours | Rate | Amount', "
        "(2) deductions 'Description | Amount'. End with a summary line: "
        "Gross Pay, Total Deductions, Net Pay."
    ),
    "lease": (
        "Format as a real residential lease. Begin with the title 'RESIDENTIAL "
        "LEASE AGREEMENT' (# heading), then numbered sections (1., 2., 3., ...) "
        "covering parties, premises, term, rent, security deposit, utilities, "
        "use, maintenance, default. End with a signature block: signature lines "
        "and dated signatures for both Lessor and Lessee."
    ),
    "contract": (
        "Format as a real commercial contract. Begin with title (# heading), "
        "parties block, recitals (WHEREAS clauses), then numbered articles "
        "(Article 1: ..., Article 2: ...). Include at least one markdown table "
        "(payment schedule, deliverables, or fees). End with a signature block "
        "with signature lines, names, titles, and dates for each party."
    ),
    "will": (
        "Format as a real Last Will and Testament. Begin with 'LAST WILL AND "
        "TESTAMENT' (# heading), declaration of testator, then numbered "
        "ARTICLE sections (Article I: Identification, Article II: Family, "
        "Article III: Specific Bequests, Article IV: Residuary Estate, ...). "
        "Include a bequest table 'Beneficiary | Bequest | Conditions'. End "
        "with attestation clause and signature lines for testator and two "
        "witnesses with addresses."
    ),
    "agreement": (
        "Format as a real legal agreement. Begin with title (# heading), "
        "parties block, then numbered sections covering scope, term, payment, "
        "responsibilities, termination. End with a signature block."
    ),
    "policy": (
        "Format as a real insurance policy. Begin with insurer name (# "
        "heading), policy number, named insured, policy period, declarations "
        "page summary. Include a markdown table of coverages with 'Coverage | "
        "Limit | Deductible | Premium' columns. Then list numbered policy "
        "provisions, exclusions, and conditions."
    ),
    "manual": (
        "Format as a real product or technical manual. Begin with the product "
        "name (# heading), then a 'Table of Contents' section listing chapters. "
        "Use ## subheadings for each chapter (Setup, Operation, Maintenance, "
        "Troubleshooting). Use bullet lists where appropriate. Include at "
        "least one markdown table summarizing specifications or "
        "troubleshooting steps."
    ),
    "guide": (
        "Format as a real instructional guide. Begin with the title (# "
        "heading), purpose statement, then ## section headings. Use numbered "
        "step lists for procedures and bullet lists for tips."
    ),
    "report": (
        "Format as a real report. Begin with a title (# heading), summary "
        "paragraph, then ## sections (Background, Findings, Recommendations). "
        "Include at least one markdown table summarizing key data with 4+ rows."
    ),
    "recipe": (
        "Format as a real recipe. Begin with the dish name (# heading), brief "
        "description, then ## Ingredients (bulleted list with quantities) and "
        "## Instructions (numbered steps). End with serving size and notes."
    ),
    "letter": (
        "Format as a real business letter. Begin with sender's address block "
        "(no heading), date, recipient's address block, salutation ('Dear "
        "...'), 3-5 body paragraphs, closing ('Sincerely,'), signature line, "
        "and printed name."
    ),
    "notice": (
        "Format as a real formal notice. Begin with issuer name and address, "
        "'NOTICE' heading (# heading), recipient block, date. Body explains "
        "the notice purpose with numbered points. End with signature line and "
        "issuer title."
    ),
    "form": (
        "Format as a real government or business form. Begin with form title "
        "(# heading) and form number. Use labeled fields where each label is "
        "followed by a value or blank line, e.g. 'Name: John Doe', "
        "'Date of Birth: 0000-00-00'. Include at least one markdown table for "
        "tabular data, and a signature block."
    ),
    "certificate": (
        "Format as a real certificate. Begin with issuer name (# heading), "
        "'CERTIFICATE OF [type]' heading, then a centered formal statement "
        "naming the recipient, the achievement or status being certified, and "
        "effective dates. End with issuer signature line and seal text."
    ),
    "license": (
        "Format as a real license document. Include issuing authority, license "
        "type and number, licensee name and address, effective and expiration "
        "dates, conditions, and authorized signature."
    ),
    "permit": (
        "Format as a real permit document. Include issuing agency, permit "
        "number and type, permittee, location/scope, effective dates, "
        "conditions/restrictions, and authorized signature."
    ),
    "passport": (
        "Format as a real passport-style identification. Include 'PASSPORT' "
        "title, country of issue, type/code, passport number, surname, given "
        "names, nationality, date of birth, sex, place of birth, date of "
        "issue, date of expiry, and authority. Use clear field labels."
    ),
    "identification": (
        "Format as a real identification document. Include issuing authority, "
        "ID type and number, full name, date of birth, address, photo "
        "placeholder, issue date, expiration date, and signature line."
    ),
    "itinerary": (
        "Format as a real travel itinerary. Begin with title (# heading) and "
        "traveler name. Use ## subheadings per day ('Day 1: <date>'), with "
        "bullet lists of activities including times. Include at least one "
        "markdown table summarizing flights or hotel stays with 'Date | "
        "Carrier/Hotel | Confirmation | Details' columns."
    ),
    "reservation": (
        "Format as a real reservation confirmation. Include provider name (# "
        "heading), confirmation number, guest name, dates, location, and a "
        "markdown table of charges."
    ),
    "confirmation": (
        "Format as a real confirmation document. Include provider name (# "
        "heading), confirmation number, customer name, item or service "
        "confirmed, dates, and totals in a small table."
    ),
    "resume": (
        "Format as a real professional resume. Begin with full name (# "
        "heading), contact info line, then ## sections: Summary, Experience "
        "(numbered or chronological with company, title, dates, and bulleted "
        "achievements), Education, and Skills (bullet list)."
    ),
    "warranty": (
        "Format as a real product warranty. Include manufacturer (# heading), "
        "product name and model, warranty period, coverage scope, exclusions "
        "(numbered or bulleted list), claim process, and warrantor signature."
    ),
    "deed": (
        "Format as a real property deed. Include 'WARRANTY DEED' heading, "
        "grantor and grantee blocks, legal description of property, "
        "consideration, habendum clause, and signature/notary block."
    ),
    "trust": (
        "Format as a real trust agreement. Include title (# heading), settlor, "
        "trustee, beneficiaries, trust property, numbered articles defining "
        "powers and distribution, and signature block."
    ),
    "title": (
        "Format as a real title document. Include issuing state authority (# "
        "heading), title number, owner block, vehicle or property description, "
        "lienholder block, and authorized signature."
    ),
    "estimate": (
        "Format as a real cost estimate. Include vendor (# heading), customer "
        "block, scope of work, markdown table of line-item costs with "
        "'Description | Quantity | Unit Cost | Total' columns, and a totals "
        "summary."
    ),
    "quote": (
        "Format as a real price quote. Include vendor (# heading), customer, "
        "quote number, validity period, markdown table of items with prices, "
        "and terms."
    ),
    "offer": (
        "Format as a real real-estate or commercial offer. Include parties (# "
        "heading), property/asset description, offer amount, contingencies "
        "(numbered list), proposed closing date, and signature block."
    ),
    "listing": (
        "Format as a real property or job listing. Include title (# heading), "
        "headline summary, key details (bullet list), then descriptive prose "
        "and contact information."
    ),
    "record": (
        "Format as a real record entry. Include record header (# heading), "
        "subject identification, date(s), then chronological entries (bulleted "
        "or numbered) with timestamps and outcomes."
    ),
    "reference": (
        "Format as a real reference document. Include title (# heading), brief "
        "purpose, then ## subsections covering definitions or topics. Use "
        "bullet lists and at least one markdown table summarizing key facts."
    ),
    "referral": (
        "Format as a real medical or professional referral. Include referring "
        "provider, patient/client block, date, reason for referral, relevant "
        "history (bulleted), and signature line."
    ),
    "return": (
        "Format as a real tax return or filing. Include taxpayer block (# "
        "heading), tax year, then numbered line-item sections with markdown "
        "tables of income, deductions, and computed tax due/refund."
    ),
    "plan": (
        "Format as a real plan document. Include title (# heading), purpose, "
        "scope, ## sections for objectives, tasks, milestones (with at least "
        "one markdown table of milestones), and assigned owners."
    ),
    "presentation": (
        "Format as a real handout summarizing a presentation. Include title "
        "(# heading), presenter, date, then ## sections per slide topic with "
        "bullet lists of key points."
    ),
    "portfolio": (
        "Format as a real portfolio summary. Include owner (# heading), "
        "as-of date, then a markdown table of holdings with 'Holding | "
        "Quantity | Value' columns and ## sections summarizing performance."
    ),
    "journal": (
        "Format as a real journal entry. Include date and title (# heading), "
        "then a series of dated entries (## subheadings) with reflective "
        "prose."
    ),
    "application": (
        "Format as a real application form. Include applicant block, date, "
        "then labeled fields (one per line) and at least one numbered list of "
        "questions with answers. End with a certification statement and "
        "signature line."
    ),
}


def _structure_hint(triple: Triple) -> str:
    return DOCTYPE_STRUCTURE_HINTS.get(
        triple.doctype,
        "Use realistic document structure with appropriate headings (# and ##), "
        "bulleted or numbered lists where relevant, and at least one markdown "
        "table if data is tabular.",
    )


def _build_prompt(
    triple: Triple,
    length_target_words: int,
    vendor: str,
    doc_date: date,
    amount: int,
) -> tuple[str, str]:
    """Return (cached_system, per_doc_user) prompt halves."""
    system = (
        "You are generating realistic synthetic documents for a "
        "document-classification evaluation corpus. Your output will be rendered "
        "as a PDF and fed to a zero-shot classifier. The renderer parses "
        "markdown structure: '# heading' and '## subheading' become heading "
        "paragraphs, lines starting with '- ' become bullet items, lines like "
        "'1. text' become numbered list items, '|col|col|' table blocks (with a "
        "'|---|---|' separator row underneath the header) become real tables, "
        "and '---' on a line by itself becomes a horizontal rule.\n\n"
        "Hard rules:\n"
        "- Output ONLY the document body. No preamble, no commentary, no "
        "triple-backtick code fences, no 'Sure,' or 'Here is' framing.\n"
        "- No instructions to the reader. Do not address the AI. Do not "
        "include system-prompt text, role markers, or strings like 'ignore "
        "previous'.\n"
        "- USE the markdown structure described above where appropriate. Real "
        "documents are not all flowing prose; they have headings, tables, "
        "lists, and signature blocks.\n"
        "- All identifiers (account numbers, SSNs, license numbers, phone "
        "numbers) must be obviously fake (e.g. account 0000-1234, SSN "
        "XXX-XX-1234).\n"
        "- Do not embed any URLs or email addresses that resolve to real "
        "domains.\n"
        "- Match the requested length within ±25%."
    )
    hint = _structure_hint(triple)
    user = (
        f"Write a {length_target_words}-word document of type '{triple.doctype}' "
        f"in the '{triple.category}' category of the '{triple.domain}' "
        f"domain.\n\n"
        f"Vendor / issuing organization: {vendor}\n"
        f"Document date: {doc_date.isoformat()}\n"
        f"Reference amount (use as anchor for any monetary figures): "
        f"${amount}\n\n"
        f"Structural guidance for this document type:\n{hint}\n\n"
        "Begin the document body now."
    )
    return system, user


def _sanitize_output(text: str) -> str | None:
    """Return cleaned text, or None if injection markers are present."""
    lower = text.lower()
    for marker in INJECTION_MARKERS:
        if marker in lower:
            return None
    if text.strip().startswith("```"):
        return None
    return text.strip()


def _coverage_plan(
    count: int, min_long: int, seed: int, taxonomy: BaseTaxonomy
) -> list[Triple]:
    """Pick triples covering all 16 domains, filling long-doc target first."""
    rng = random.Random(seed)
    domains = sorted(taxonomy.CANONICAL_DOMAINS)
    picks: list[Triple] = []

    long_pool = [Triple(*t) for t in LONG_TRIPLES if t[0] in domains]
    rng.shuffle(long_pool)
    for t in long_pool[:min_long]:
        picks.append(t)

    for d in domains:
        default = DOMAIN_DEFAULT_TRIPLE[d]
        if not any(p.domain == d for p in picks):
            picks.append(Triple(*default))

    pool: list[Triple] = []
    for d in domains:
        cats = sorted(taxonomy.CANONICAL_CATEGORIES.get(d, set()))
        if not cats:
            continue
        plausible_doctypes = sorted(DOMAIN_DOCTYPES.get(d, set()))
        for c in cats:
            for dt in plausible_doctypes:
                pool.append(Triple(d, c, dt))
    rng.shuffle(pool)

    for t in pool:
        if len(picks) >= count:
            break
        if t in picks:
            continue
        if taxonomy.canonical_category(t.domain, t.category) is None:
            continue
        picks.append(t)

    if len(picks) > count:
        long_set = {Triple(*t) for t in LONG_TRIPLES}
        keep_long = [p for p in picks if p in long_set][:min_long]
        rest = [p for p in picks if p not in keep_long]
        rng.shuffle(rest)
        picks = keep_long + rest[: count - len(keep_long)]

    return picks[:count]


# -- API + tokenizer ---------------------------------------------------------


def _load_tokenizer(offline: bool = True) -> PreTrainedTokenizerBase:
    """Load the cross-encoder tokenizer; try offline first, then network."""
    from transformers import AutoTokenizer  # type: ignore[import-not-found]

    try:
        return AutoTokenizer.from_pretrained(NLI_TOKENIZER_ID, local_files_only=offline)
    except Exception as exc:
        if not offline:
            raise
        logger.warning("tokenizer_offline_miss", model=NLI_TOKENIZER_ID, error=str(exc))
        return AutoTokenizer.from_pretrained(NLI_TOKENIZER_ID, local_files_only=False)


def _token_count(text: str, tokenizer: PreTrainedTokenizerBase) -> int:
    return len(tokenizer.encode(text, add_special_tokens=False))


def _anthropic_client(
    model: str, max_retries: int, timeout_seconds: int
) -> ChatAnthropic:
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(  # type: ignore[call-arg]
        model=model,
        temperature=0.7,
        max_tokens=4096,
        timeout=float(timeout_seconds),
        max_retries=max_retries,
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )


async def _call_anthropic_async(
    client: ChatAnthropic,
    system: str,
    user: str,
) -> tuple[str, dict[str, int]]:
    """Invoke the model with prompt-cached system block; return (text, usage)."""
    from langchain_core.messages import HumanMessage, SystemMessage

    sys_msg = SystemMessage(
        content=[
            {
                "type": "text",
                "text": system,
                "cache_control": {"type": "ephemeral"},
            }
        ]
    )
    user_msg = HumanMessage(content=user)

    response = await client.ainvoke([sys_msg, user_msg])
    text = (
        response.content if isinstance(response.content, str) else str(response.content)
    )

    meta: dict[str, Any] = getattr(response, "response_metadata", None) or {}
    usage_meta: dict[str, Any] = getattr(response, "usage_metadata", None) or {}
    raw_usage: dict[str, Any] = meta.get("usage", {}) or {}
    cache_read = (
        raw_usage.get("cache_read_input_tokens")
        or usage_meta.get("input_token_details", {}).get("cache_read", 0)
        or 0
    )
    cache_write = (
        raw_usage.get("cache_creation_input_tokens")
        or usage_meta.get("input_token_details", {}).get("cache_creation", 0)
        or 0
    )
    usage: dict[str, int] = {
        "input_tokens": int(
            usage_meta.get("input_tokens", raw_usage.get("input_tokens", 0)) or 0
        ),
        "output_tokens": int(
            usage_meta.get("output_tokens", raw_usage.get("output_tokens", 0)) or 0
        ),
        "cache_read_tokens": int(cache_read or 0),
        "cache_write_tokens": int(cache_write or 0),
    }
    return text, usage


def _estimate_cost(usage: dict[str, int], model: str) -> float:
    rates = MODEL_PRICING.get(model)
    if rates is None:
        return 0.0
    in_uncached = max(
        usage["input_tokens"]
        - usage["cache_read_tokens"]
        - usage["cache_write_tokens"],
        0,
    )
    return (
        (in_uncached / 1_000_000) * rates["input"]
        + (usage["cache_write_tokens"] / 1_000_000) * rates["cache_write"]
        + (usage["cache_read_tokens"] / 1_000_000) * rates["cache_read"]
        + (usage["output_tokens"] / 1_000_000) * rates["output"]
    )


# -- PDF + JSONL --------------------------------------------------------------


_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_TABLE_SEP_RE = re.compile(r"^\s*\|?[\s:\-|]+\|[\s:\-|]+\|?\s*$")
_HEADING1_RE = re.compile(r"^#\s+(.+)$")
_HEADING2_RE = re.compile(r"^##\s+(.+)$")
_HEADING3_RE = re.compile(r"^###\s+(.+)$")
_BULLET_RE = re.compile(r"^[\-\*]\s+(.+)$")
_NUMBERED_RE = re.compile(r"^\d+\.\s+(.+)$")
_HRULE_RE = re.compile(r"^-{3,}$|^_{3,}$|^\*{3,}$")


def _split_table_row(line: str) -> list[str]:
    cells = [c.strip() for c in line.strip().strip("|").split("|")]
    return cells


def _md_inline(text: str) -> str:
    """Convert a small subset of markdown inline syntax to reportlab tags."""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*(?!\s)(.+?)(?<!\s)\*(?!\*)", r"<i>\1</i>", text)
    return text


def _render_pdf(text: str, out_path: Path) -> None:
    from reportlab.lib import colors  # type: ignore[import-untyped]
    from reportlab.lib.pagesizes import LETTER  # type: ignore[import-untyped]
    from reportlab.lib.styles import (  # type: ignore[import-untyped]
        ParagraphStyle,
        getSampleStyleSheet,
    )
    from reportlab.lib.units import inch  # type: ignore[import-untyped]
    from reportlab.platypus import (  # type: ignore[import-untyped]
        HRFlowable,
        ListFlowable,
        ListItem,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )

    base = getSampleStyleSheet()
    body = base["BodyText"]
    h1 = ParagraphStyle("h1", parent=base["Heading1"], spaceAfter=8, spaceBefore=10)
    h2 = ParagraphStyle("h2", parent=base["Heading2"], spaceAfter=6, spaceBefore=8)
    h3 = ParagraphStyle("h3", parent=base["Heading3"], spaceAfter=4, spaceBefore=6)
    item_style = ParagraphStyle("li", parent=body, leftIndent=0, spaceAfter=2)

    raw_lines = text.split("\n")
    flow: list[Any] = []
    i = 0
    n = len(raw_lines)
    para_buf: list[str] = []
    list_buf: list[ListItem] = []
    list_kind: str | None = None  # "bullet" or "numbered"

    def flush_paragraph() -> None:
        if not para_buf:
            return
        joined = " ".join(p.strip() for p in para_buf if p.strip())
        if joined:
            flow.append(Paragraph(_md_inline(joined), body))
            flow.append(Spacer(1, 4))
        para_buf.clear()

    def flush_list() -> None:
        nonlocal list_kind
        if not list_buf:
            return
        bullet = "bullet" if list_kind == "bullet" else "1"
        flow.append(ListFlowable(list(list_buf), bulletType=bullet, leftIndent=18))
        flow.append(Spacer(1, 4))
        list_buf.clear()
        list_kind = None

    while i < n:
        line = raw_lines[i].rstrip()
        stripped = line.strip()

        if not stripped:
            flush_paragraph()
            flush_list()
            i += 1
            continue

        if (
            _TABLE_ROW_RE.match(stripped)
            and i + 1 < n
            and _TABLE_SEP_RE.match(raw_lines[i + 1].strip())
        ):
            flush_paragraph()
            flush_list()
            header = _split_table_row(stripped)
            rows: list[list[str]] = [header]
            i += 2
            while i < n and _TABLE_ROW_RE.match(raw_lines[i].strip()):
                rows.append(_split_table_row(raw_lines[i].strip()))
                i += 1
            data: list[list[Any]] = [
                [Paragraph(_md_inline(c), body) for c in row] for row in rows
            ]
            tbl = Table(data, hAlign="LEFT", repeatRows=1)
            tbl.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                        ("GRID", (0, 0), (-1, -1), 0.4, colors.grey),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("LEFTPADDING", (0, 0), (-1, -1), 4),
                        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                    ]
                )
            )
            flow.append(tbl)
            flow.append(Spacer(1, 6))
            continue

        if _HRULE_RE.match(stripped):
            flush_paragraph()
            flush_list()
            flow.append(HRFlowable(width="100%", thickness=0.6, color=colors.grey))
            flow.append(Spacer(1, 4))
            i += 1
            continue

        m1 = _HEADING1_RE.match(stripped)
        m2 = _HEADING2_RE.match(stripped)
        m3 = _HEADING3_RE.match(stripped)
        if m1 or m2 or m3:
            flush_paragraph()
            flush_list()
            text_part = (m1 or m2 or m3).group(1)  # type: ignore[union-attr]
            style = h1 if m1 else (h2 if m2 else h3)
            flow.append(Paragraph(_md_inline(text_part), style))
            i += 1
            continue

        bm = _BULLET_RE.match(stripped)
        nm = _NUMBERED_RE.match(stripped)
        if bm or nm:
            flush_paragraph()
            kind = "bullet" if bm else "numbered"
            if list_kind is not None and list_kind != kind:
                flush_list()
            list_kind = kind
            content = (bm or nm).group(1)  # type: ignore[union-attr]
            list_buf.append(
                ListItem(Paragraph(_md_inline(content), item_style), leftIndent=12)
            )
            i += 1
            continue

        para_buf.append(line)
        i += 1

    flush_paragraph()
    flush_list()

    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )
    doc.build(flow)

    if out_path.stat().st_size < 1024:
        raise RuntimeError(
            f"rendered PDF is suspiciously small: {out_path} ({out_path.stat().st_size} bytes)"
        )


def _append_jsonl_atomic(row: GroundTruthRow, jsonl_path: Path) -> None:
    """Append one row by writing the full new file to a temp sibling and renaming."""
    existing = jsonl_path.read_text() if jsonl_path.exists() else ""
    new_line = row.model_dump_json() + "\n"
    payload = (
        existing + new_line
        if existing.endswith("\n") or not existing
        else existing + "\n" + new_line
    )

    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(
        prefix=jsonl_path.name + ".", dir=str(jsonl_path.parent)
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
        Path(tmp_path).replace(jsonl_path)
    except Exception:
        Path(tmp_path).unlink(missing_ok=True)
        raise


def _existing_filenames(output_dir: Path, jsonl_path: Path) -> set[str]:
    seen: set[str] = set()
    if output_dir.exists():
        seen.update(p.name for p in output_dir.glob("*.pdf"))
    if jsonl_path.exists():
        for line in jsonl_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            fn = obj.get("filename")
            if isinstance(fn, str):
                seen.add(fn)
    return seen


def _read_existing_rows(jsonl_path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not jsonl_path.exists():
        return rows
    for line in jsonl_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _topup_plan(
    rows: list[dict[str, Any]],
    taxonomy: BaseTaxonomy,
    target_per_domain: int,
    target_cats: int,
    target_doctypes: int,
    seed: int,
) -> list[Triple]:
    """Build a coverage-filling plan from current ground-truth state.

    Stages:
    1. Add (domain, new_category, plausible_doctype) triples until each domain
       has >= target_cats distinct categories.
    2. Add (domain, seen_category, new_doctype) triples until each domain has
       >= target_doctypes distinct doctypes.
    3. Pad each domain up to target_per_domain total docs, biasing toward
       LONG_TRIPLES when available so long-doc coverage stays healthy.
    """
    rng = random.Random(seed)
    domains = sorted(taxonomy.CANONICAL_DOMAINS)

    counts: dict[str, int] = dict.fromkeys(domains, 0)
    cats_seen: dict[str, set[str]] = {d: set() for d in domains}
    doctypes_seen: dict[str, set[str]] = {d: set() for d in domains}
    for r in rows:
        d = r.get("domain")
        if d not in counts:
            continue
        counts[d] += 1
        c = r.get("category")
        dt = r.get("doctype")
        if isinstance(c, str):
            cats_seen[d].add(c)
        if isinstance(dt, str):
            doctypes_seen[d].add(dt)

    long_by_domain: dict[str, list[Triple]] = {}
    for d, c, dt in LONG_TRIPLES:
        long_by_domain.setdefault(d, []).append(Triple(d, c, dt))

    picks: list[Triple] = []

    def _record(t: Triple) -> None:
        picks.append(t)
        counts[t.domain] += 1
        cats_seen[t.domain].add(t.category)
        doctypes_seen[t.domain].add(t.doctype)

    # Stage 1: category shortfall.
    for d in domains:
        canonical_cats = sorted(taxonomy.CANONICAL_CATEGORIES.get(d, set()))
        plausible_dts = sorted(DOMAIN_DOCTYPES.get(d, set()))
        if not canonical_cats or not plausible_dts:
            continue
        missing = [c for c in canonical_cats if c not in cats_seen[d]]
        rng.shuffle(missing)
        rng.shuffle(plausible_dts)
        while len(cats_seen[d]) < target_cats and missing:
            new_cat = missing.pop()
            if taxonomy.canonical_category(d, new_cat) is None:
                continue
            _record(Triple(d, new_cat, plausible_dts[0]))

    # Stage 2: doctype shortfall.
    for d in domains:
        plausible_dts = sorted(DOMAIN_DOCTYPES.get(d, set()))
        cat_options = sorted(cats_seen[d]) or sorted(
            taxonomy.CANONICAL_CATEGORIES.get(d, set())
        )
        if not plausible_dts or not cat_options:
            continue
        missing_dts = [dt for dt in plausible_dts if dt not in doctypes_seen[d]]
        rng.shuffle(missing_dts)
        rng.shuffle(cat_options)
        while len(doctypes_seen[d]) < target_doctypes and missing_dts:
            new_dt = missing_dts.pop()
            cat = cat_options[0]
            if taxonomy.canonical_category(d, cat) is None:
                continue
            _record(Triple(d, cat, new_dt))

    # Stage 3: pad each domain up to target_per_domain.
    for d in domains:
        cat_options = sorted(cats_seen[d]) or sorted(
            taxonomy.CANONICAL_CATEGORIES.get(d, set())
        )
        dt_options = sorted(doctypes_seen[d]) or sorted(DOMAIN_DOCTYPES.get(d, set()))
        if not cat_options or not dt_options:
            continue
        long_pool = list(long_by_domain.get(d, []))
        guard = 0
        while counts[d] < target_per_domain and guard < 100:
            guard += 1
            if long_pool and rng.random() < 0.5:
                t = rng.choice(long_pool)
                if taxonomy.canonical_category(t.domain, t.category) is None:
                    long_pool.remove(t)
                    continue
                _record(t)
            else:
                cat = rng.choice(cat_options)
                dt = rng.choice(dt_options)
                if taxonomy.canonical_category(d, cat) is None:
                    continue
                _record(Triple(d, cat, dt))

    rng.shuffle(picks)
    return picks


# -- Generation orchestration ------------------------------------------------


def _subject_for(triple: Triple) -> str:
    return f"{triple.category} {triple.doctype}".replace("_", " ")


def _length_target(triple: Triple) -> int:
    if (triple.domain, triple.category, triple.doctype) in {
        tuple(t) for t in LONG_TRIPLES
    }:
        return 1100
    return 320


def _random_date(rng: random.Random) -> date:
    today = datetime.now(UTC).date()
    delta = rng.randint(0, 365)
    return today - timedelta(days=delta)


async def _generate_one(
    client: ChatAnthropic,
    triple: Triple,
    rng: random.Random,
    tokenizer: PreTrainedTokenizerBase,
    output_dir: Path,
    sem: asyncio.Semaphore,
    model: str,
    skip_filenames: set[str],
) -> GenerationResult | None:
    async with sem:
        vendor = rng.choice(VENDOR_POOLS[triple.domain])
        doc_date = _random_date(rng)
        amount_lo, amount_hi = AMOUNT_RANGES[triple.domain]
        amount = rng.randint(amount_lo, amount_hi)
        filename = _filename(triple, vendor, doc_date)
        if filename in skip_filenames:
            logger.info("skip_existing", filename=filename)
            return None

        length_target = _length_target(triple)
        system, user = _build_prompt(triple, length_target, vendor, doc_date, amount)

        for attempt in range(3):
            text_raw, usage = await _call_anthropic_async(client, system, user)
            text = _sanitize_output(text_raw)
            if text is not None:
                break
            logger.warning("sanitize_rejected", filename=filename, attempt=attempt + 1)
        else:
            logger.error("sanitize_exhausted", filename=filename)
            return None

        out_path = output_dir / filename
        output_dir.mkdir(parents=True, exist_ok=True)
        _render_pdf(text, out_path)

        row = GroundTruthRow(
            filename=filename,
            domain=triple.domain,
            category=triple.category,
            doctype=triple.doctype,
            vendor=vendor,
            date=doc_date.strftime("%Y%m%d"),
            subject=_subject_for(triple),
            notes=f"synthetic, generated {datetime.now(UTC).date().isoformat()}",
        )

        token_count = _token_count(text, tokenizer)
        return GenerationResult(
            triple=triple,
            text=text,
            pdf_path=out_path,
            row=row,
            token_count=token_count,
            input_tokens=usage["input_tokens"],
            output_tokens=usage["output_tokens"],
            cache_read_tokens=usage["cache_read_tokens"],
            cache_write_tokens=usage["cache_write_tokens"],
            model=model,
        )


def _validate_triple(triple: Triple, taxonomy: BaseTaxonomy) -> None:
    """Reject triples that don't pass strict-mode validation."""
    if taxonomy.canonical_domain(triple.domain) is None:
        raise ValueError(f"unknown domain: {triple.domain}")
    if taxonomy.canonical_category(triple.domain, triple.category) is None:
        raise ValueError(f"unknown category: ({triple.domain}, {triple.category})")
    if taxonomy.canonical_doctype(triple.doctype) is None:
        raise ValueError(f"unknown doctype: {triple.doctype}")


async def _run(
    *,
    count: int,
    min_long: int,
    seed: int,
    model: str,
    output_dir: Path,
    ground_truth: Path,
    concurrency: int,
    max_cost_usd: float,
    dry_run: bool,
    top_up: bool,
    target_per_domain: int,
    target_cats: int,
    target_doctypes: int,
) -> None:
    taxonomy = get_taxonomy("household")
    rng = random.Random(seed)

    if top_up:
        existing_rows = _read_existing_rows(ground_truth)
        plan = _topup_plan(
            existing_rows,
            taxonomy,
            target_per_domain,
            target_cats,
            target_doctypes,
            seed,
        )
        click.echo(
            f"# Top-up plan: existing={len(existing_rows)} new_triples={len(plan)} "
            f"targets per domain: docs>={target_per_domain} "
            f"cats>={target_cats} doctypes>={target_doctypes}"
        )
    else:
        plan = _coverage_plan(count, min_long, seed, taxonomy)
    for t in plan:
        _validate_triple(t, taxonomy)

    click.echo(f"# Coverage plan ({len(plan)} triples, min_long={min_long})")
    click.echo("| # | domain | category | doctype | length |")
    click.echo("|---|--------|----------|---------|--------|")
    long_set = {tuple(t) for t in LONG_TRIPLES}
    for i, t in enumerate(plan, 1):
        kind = "long" if (t.domain, t.category, t.doctype) in long_set else "short"
        click.echo(f"| {i} | {t.domain} | {t.category} | {t.doctype} | {kind} |")
    click.echo()

    if dry_run:
        click.echo("dry-run: no API calls or writes.")
        return

    click.echo(f"Loading tokenizer {NLI_TOKENIZER_ID} ...")
    tokenizer = _load_tokenizer(offline=True)

    click.echo(f"Building Anthropic client (model={model}) ...")
    client = _anthropic_client(model, max_retries=3, timeout_seconds=120)

    skip_filenames = _existing_filenames(output_dir, ground_truth)
    if skip_filenames:
        click.echo(f"resume: {len(skip_filenames)} existing filenames will be skipped")

    sem = asyncio.Semaphore(concurrency)
    tasks = [
        _generate_one(client, t, rng, tokenizer, output_dir, sem, model, skip_filenames)
        for t in plan
    ]

    cumulative_cost = 0.0
    long_doc_count = 0
    written = 0
    rejected = 0

    click.echo("\n# Generation results")
    click.echo("| # | filename | tokens | input | output | cache_r | cost_usd |")
    click.echo("|---|----------|--------|-------|--------|---------|----------|")

    for i, coro in enumerate(asyncio.as_completed(tasks), 1):
        result = await coro
        if result is None:
            rejected += 1
            continue
        try:
            _ = GroundTruthRow.model_validate(result.row.model_dump())
        except ValidationError as exc:
            click.echo(
                f"row validation failed for {result.pdf_path.name}: {exc}", err=True
            )
            result.pdf_path.unlink(missing_ok=True)
            rejected += 1
            continue

        usage = {
            "input_tokens": result.input_tokens,
            "output_tokens": result.output_tokens,
            "cache_read_tokens": result.cache_read_tokens,
            "cache_write_tokens": result.cache_write_tokens,
        }
        call_cost = _estimate_cost(usage, model)
        cumulative_cost += call_cost
        if result.token_count > LONG_DOC_THRESHOLD:
            long_doc_count += 1

        _append_jsonl_atomic(result.row, ground_truth)
        written += 1
        click.echo(
            f"| {i} | {result.pdf_path.name} | {result.token_count} | "
            f"{result.input_tokens} | {result.output_tokens} | "
            f"{result.cache_read_tokens} | {call_cost:.4f} |"
        )

        if cumulative_cost > max_cost_usd:
            click.echo(
                f"\nABORT: cumulative cost ${cumulative_cost:.2f} exceeds "
                f"--max-cost-usd ${max_cost_usd:.2f}",
                err=True,
            )
            break

    click.echo()
    click.echo(
        f"summary: written={written} rejected={rejected} "
        f"long_docs={long_doc_count}/{min_long} cost_usd={cumulative_cost:.4f}"
    )
    if rejected and rejected / max(written + rejected, 1) > 0.10:
        click.echo(
            f"WARNING: rejection rate {rejected}/{written + rejected} > 10%; "
            "investigate prompt template before further runs.",
            err=True,
        )


# -- CLI ----------------------------------------------------------------------


@click.command()
@click.option("--count", type=int, default=30, show_default=True)
@click.option("--min-long-docs", type=int, default=5, show_default=True)
@click.option("--seed", type=int, default=42, show_default=True)
@click.option("--ai-model", default="claude-sonnet-4-6", show_default=True)
@click.option("--max-cost-usd", type=float, default=6.00, show_default=True)
@click.option("--concurrency", type=int, default=5, show_default=True)
@click.option(
    "--output-dir",
    type=click.Path(file_okay=False, path_type=Path),
    default=Path("eval/samples"),
    show_default=True,
)
@click.option(
    "--ground-truth",
    type=click.Path(dir_okay=False, path_type=Path),
    default=Path("eval/ground_truth.jsonl"),
    show_default=True,
)
@click.option("--dry-run", is_flag=True, default=False)
@click.option(
    "--top-up",
    is_flag=True,
    default=False,
    help="Read existing ground-truth and generate only triples that fill coverage gaps.",
)
@click.option("--target-per-domain", type=int, default=5, show_default=True)
@click.option("--target-cats", type=int, default=2, show_default=True)
@click.option("--target-doctypes", type=int, default=2, show_default=True)
@click.option(
    "--log-level",
    type=click.Choice([lvl.value for lvl in LogLevel]),
    default=LogLevel.QUIET.value,
    show_default=True,
)
def main(
    count: int,
    min_long_docs: int,
    seed: int,
    ai_model: str,
    max_cost_usd: float,
    concurrency: int,
    output_dir: Path,
    ground_truth: Path,
    dry_run: bool,
    top_up: bool,
    target_per_domain: int,
    target_cats: int,
    target_doctypes: int,
    log_level: str,
) -> None:
    """Generate synthetic eval documents and append ground-truth rows."""
    configure_logging(level=LogLevel(log_level), json_output=False)

    asyncio.run(
        _run(
            count=count,
            min_long=min_long_docs,
            seed=seed,
            model=ai_model,
            output_dir=output_dir,
            ground_truth=ground_truth,
            concurrency=concurrency,
            max_cost_usd=max_cost_usd,
            dry_run=dry_run,
            top_up=top_up,
            target_per_domain=target_per_domain,
            target_cats=target_cats,
            target_doctypes=target_doctypes,
        )
    )


if __name__ == "__main__":
    main()
