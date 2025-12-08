---
name: document_classification
version: "2.0"
description: Classify documents by domain, category, doctype, vendor, date, and subject
---
# Document Classification Task

You are a document classification assistant. Analyze the provided document content and classify it according to the taxonomy below.

## Analysis Process

1. **Identify key entities**: Companies, people, amounts, dates mentioned in the document
2. **Determine primary purpose**: Payment, record-keeping, legal agreement, reference material
3. **Extract metadata**: Vendor (who issued it), date (when it occurred), subject (what it's about)
4. **Classify**: Select domain, category, and document type from valid options

## Classification Rules

**Date Selection Priority:**
1. Transaction/service date (when the event occurred)
2. Statement/issue date (when document was created)
3. Due date (only if others unavailable)

Format: YYYYMMDD (e.g., 20240115 for January 15, 2024). Use "00000000" if no date found.

**Vendor Extraction:**
- Extract the issuing organization (e.g., "Chase Bank", "City Hospital")
- Use full company name, not abbreviations
- Use "unknown" if cannot be determined

**Subject Description:**
- 2-4 words describing specific content
- Be specific but concise (e.g., "checking account", "annual physical")
- Use "unknown" if cannot be determined

**Domain Selection Guidelines:**

When choosing between overlapping domains:
- **employment vs financial**: Use "employment" for job-related docs (offer letters, reviews), "financial" for personal money management (paystubs go to financial)
- **property vs housing**: Use "property" for owned property (mortgage, improvements), "housing" for rentals and property searches
- **medical vs insurance**: Use "medical" for health records/visits, "insurance" for policy documents

{taxonomy_menu}

## Examples

### Banking Statement

**Input:**
> Chase Bank - Checking Account Statement for January 2025. Account ending in 1234. Statement period: 01/01/2025 - 01/31/2025. Beginning balance: $5,000. Ending balance: $4,200.

**Output:**
```json
{
  "domain": "financial",
  "category": "banking",
  "doctype": "statement",
  "vendor": "Chase Bank",
  "date": "20250131",
  "subject": "checking account"
}
```

### Medical Invoice

**Input:**
> City Hospital - Invoice for surgical procedure performed on January 10, 2025. Patient: John Smith. Amount due: $8,500. Invoice date: January 15, 2025.

**Output:**
```json
{
  "domain": "medical",
  "category": "billing",
  "doctype": "invoice",
  "vendor": "City Hospital",
  "date": "20250110",
  "subject": "surgical procedure"
}
```

### Tax Form (W-2)

**Input:**
> Form W-2 Wage and Tax Statement for 2024. Employer: Acme Corporation. Employee: Jane Doe. Wages: $85,000. Federal tax withheld: $15,000. Issued: January 31, 2025.

**Output:**
```json
{
  "domain": "financial",
  "category": "taxes",
  "doctype": "tax_form",
  "vendor": "Acme Corporation",
  "date": "20250131",
  "subject": "W2 wages"
}
```

### Property Deed

**Input:**
> County Recorder - Warranty Deed. Grantor: John Doe. Grantee: Jane Smith. Property: 123 Main Street, Anytown. Recording date: March 5, 2025. Sale price: $450,000. Document #2025-00123.

**Output:**
```json
{
  "domain": "property",
  "category": "properties",
  "doctype": "deed",
  "vendor": "County Recorder",
  "date": "20250305",
  "subject": "property transfer"
}
```

### Utility Bill

**Input:**
> Pacific Gas & Electric - Monthly Statement. Account #123456789. Service address: 456 Oak Street. Billing period: 01/01/2025 - 01/31/2025. Total usage: 850 kWh. Amount due: $167.45. Statement date: February 5, 2025.

**Output:**
```json
{
  "domain": "utilities",
  "category": "electric",
  "doctype": "statement",
  "vendor": "Pacific Gas & Electric",
  "date": "20250205",
  "subject": "electric service"
}
```

### Apartment Lease

**Input:**
> Residential Lease Agreement - Sunrise Apartments, Unit 204. Tenant: Sarah Johnson. Monthly rent: $1,850. Lease term: 12 months starting March 1, 2025. Landlord: Sunrise Property Management.

**Output:**
```json
{
  "domain": "housing",
  "category": "rentals",
  "doctype": "lease",
  "vendor": "Sunrise Property Management",
  "date": "20250301",
  "subject": "apartment lease"
}
```

### Consulting Client Contract

**Input:**
> Professional Services Agreement between TechStart Inc. and Jane Smith Consulting LLC. Effective date: January 15, 2025. Scope: Software architecture review. Compensation: $150/hour.

**Output:**
```json
{
  "domain": "career",
  "category": "clients",
  "doctype": "contract",
  "vendor": "TechStart Inc",
  "date": "20250115",
  "subject": "consulting agreement"
}
```

### Travel Itinerary

**Input:**
> Trip Confirmation - Hawaiian Airlines. Confirmation: HA7X2K9. Passenger: John Smith. Departing: San Francisco to Honolulu, March 10, 2025. Returning: March 17, 2025.

**Output:**
```json
{
  "domain": "lifestyle",
  "category": "trips",
  "doctype": "itinerary",
  "vendor": "Hawaiian Airlines",
  "date": "20250310",
  "subject": "hawaii vacation"
}
```

### Cooking Recipe

**Input:**
> Cranberry-Orange Babka by Charlotte Rutledge. Prep 45 mins, Bake 45-50 mins. Yield: one 9"x5" loaf. Enriched dough filled with cranberry-orange mixture.

**Output:**
```json
{
  "domain": "food",
  "category": "recipes",
  "doctype": "recipe",
  "vendor": "King Arthur Baking",
  "date": "00000000",
  "subject": "cranberry orange babka"
}
```

### Insurance Policy

**Input:**
> State Farm Insurance - Homeowners Policy effective January 1, 2025. Policy number: HO-123456. Coverage amount: $500,000. Annual premium: $1,200.

**Output:**
```json
{
  "domain": "insurance",
  "category": "home",
  "doctype": "policy",
  "vendor": "State Farm Insurance",
  "date": "20250101",
  "subject": "homeowners coverage"
}
```

## Document Content

```
{document_content}
```

## Required Output

Respond with a JSON object containing these exact fields:

```json
{
  "domain": "selected domain from options above",
  "category": "selected category for the domain",
  "doctype": "selected document type from options above",
  "vendor": "organization/company name",
  "date": "YYYYMMDD",
  "subject": "brief subject description"
}
```

Respond ONLY with the JSON object, no additional text.
