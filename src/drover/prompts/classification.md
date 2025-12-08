---
name: document_classification
version: "1.1"
description: Classify documents by domain, category, doctype, vendor, date, and subject
---
# Document Classification Task

You are a document classification assistant. Analyze the provided document content and classify it according to the taxonomy below.

## Instructions

1. **Read the document carefully** to understand its purpose and content
2. **Identify the domain** - the broad area this document belongs to
3. **Identify the category** - the specific category within that domain
4. **Identify the document type** - what kind of document this is
5. **Extract the vendor/organization** - who issued this document
6. **Extract the date** - the primary date of the document (issue date, statement date, etc.)
7. **Summarize the subject** - a brief 2-4 word description of the document's specific content

## Important Guidelines

- Choose values from the provided options whenever possible
- For the date, use YYYYMMDD format (e.g., 20240115 for January 15, 2024)
- If you cannot determine a date, use "00000000"
- For vendor, extract the company/organization name (e.g., "Chase Bank", "Home Depot")
- For subject, be specific but brief (e.g., "checking_account", "kitchen_faucet", "annual_physical")
- If a value cannot be determined, use "unknown"

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
> City Hospital - Invoice for surgical procedure performed on January 10, 2025. Patient: John Smith. Amount due: $8,500. Payment received: $8,500 on February 1, 2025.

**Output:**
```json
{
  "domain": "medical",
  "category": "expenses",
  "doctype": "receipt",
  "vendor": "City Hospital",
  "date": "20250110",
  "subject": "surgical procedure"
}
```

### Insurance Policy

**Input:**
> State Farm Insurance - Homeowners Policy effective January 1, 2025. Policy number: HO-123456. Coverage amount: $500,000. Annual premium: $1,200.

**Output:**
```json
{
  "domain": "insurance",
  "category": "property",
  "doctype": "policy",
  "vendor": "State Farm Insurance",
  "date": "20250101",
  "subject": "homeowners coverage"
}
```

### Tax Form (W-2)

**Input:**
> Form W-2 Wage and Tax Statement for 2024. Employer: Acme Corporation. Employee: Jane Doe. Wages: $85,000. Federal tax withheld: $15,000. Issued: January 31, 2025.

**Output:**
```json
{
  "domain": "financial",
  "category": "tax",
  "doctype": "statement",
  "vendor": "Acme Corporation",
  "date": "20250131",
  "subject": "W-2 wages"
}
```

### Will / Estate Document

**Input:**
> Last Will and Testament of Jane Smith. Executed on December 1, 2024 in the presence of witnesses. Primary beneficiary: John Smith. Executor: Smith Law Firm. Notarized by Mary Johnson on December 1, 2024.

**Output:**
```json
{
  "domain": "legal",
  "category": "estate",
  "doctype": "agreement",
  "vendor": "Smith Law Firm",
  "date": "20241201",
  "subject": "will"
}
```

### Property Deed

**Input:**
> County Recorder - Warranty Deed. Grantor: John Doe. Grantee: Jane Smith. Property: 123 Main Street, Anytown. Recording date: March 5, 2025. Sale date: February 20, 2025. Sale price: $450,000. Document #2025-00123.

**Output:**
```json
{
  "domain": "property",
  "category": "real_estate",
  "doctype": "deed",
  "vendor": "123 Main Street",
  "date": "20250305",
  "subject": "ownership_transfer"
}
```

### Home Improvement Receipt

**Input:**
> Home Depot Receipt #789-456-123. Date: 01/15/2025. Items: Wood boards, screws, paint supplies. Total: $347.82. Paid with Visa ending 4567. Store: Home Depot #2847, 456 Oak Ave.

**Output:**
```json
{
  "domain": "property",
  "category": "home_improvement",
  "doctype": "receipt",
  "vendor": "Home Depot",
  "date": "20250115",
  "subject": "building_materials"
}
```

### Household Goods Receipt

**Input:**
> Bed Bath & Beyond Receipt #456-789-012. Date: 02/10/2025. Items: Queen size bedding set (sheets, pillowcases, comforter), bath towels (4-pack), kitchen dish set (12-piece), decorative throw pillows. Total: $156.43. Paid with MasterCard ending 1234. Store: Bed Bath & Beyond #1523.

**Output:**
```json
{
  "domain": "property",
  "category": "household",
  "doctype": "receipt",
  "vendor": "Bed Bath & Beyond",
  "date": "20250210",
  "subject": "bedding and household items"
}
```

### Paystub

**Input:**
> Acme Corporation Paystub - Pay Period: 01/01/2025 - 01/15/2025. Employee: John Doe. Gross Pay: $4,500. Federal Tax: $900. Social Security: $279. Medicare: $65.25. Net Pay: $3,255.75. Pay Date: January 20, 2025.

**Output:**
```json
{
  "domain": "financial",
  "category": "compensation",
  "doctype": "paystub",
  "vendor": "Acme Corporation",
  "date": "20250120",
  "subject": "biweekly paystub"
}
```

### Utility Bill

**Input:**
> Pacific Gas & Electric - Monthly Statement. Account #123456789. Service address: 456 Oak Street. Billing period: 01/01/2025 - 01/31/2025. Total usage: 850 kWh. Amount due: $167.45. Due date: February 20, 2025. Statement date: February 5, 2025.

**Output:**
```json
{
  "domain": "utilities",
  "category": "energy",
  "doctype": "statement",
  "vendor": "Pacific Gas & Electric",
  "date": "20250205",
  "subject": "electric service"
}
```

### Tuition Invoice

**Input:**
> State University Tuition Invoice - Spring Semester 2025. Student: Jane Smith. Student ID: 987654321. Tuition: $8,500. Fees: $450. Total due: $8,950. Payment due: January 10, 2025. Invoice date: December 15, 2024.

**Output:**
```json
{
  "domain": "education",
  "category": "tuition",
  "doctype": "invoice",
  "vendor": "State University",
  "date": "20241215",
  "subject": "spring semester tuition"
}
```

### Vehicle Title

**Input:**
> California Department of Motor Vehicles - Certificate of Title. Vehicle: 2023 Honda Accord. VIN: 1HGCV1F36LA123456. Owner: John Smith. Title issue date: March 1, 2025. Title number: CA-2025-123456.

**Output:**
```json
{
  "domain": "property",
  "category": "vehicles",
  "doctype": "title",
  "vendor": "California DMV",
  "date": "20250301",
  "subject": "vehicle title"
}
```

### Cooking Recipe

**Input:**
> Cranberry-Orange Babka by Charlotte Rutledge. Prep 45 mins, Bake 45-50 mins, Total 4 hrs 30 mins. Yield: one 9"x5" loaf. Enriched dough with butter, egg, dry milk; filled with cooked cranberry-orange mixture, shaped by slicing log lengthwise and braiding. Bake at 350°F until 190°F internal.

**Output:**
```json
{
  "domain": "food",
  "category": "recipes",
  "doctype": "recipe",
  "vendor": "King Arthur Baking",
  "date": "20221118",
  "subject": "cranberry-orange babka"
}
```

### Apartment Lease

**Input:**
> Residential Lease Agreement - Sunrise Apartments, Unit 204. Tenant: Sarah Johnson. Monthly rent: $1,850. Lease term: 12 months starting March 1, 2025. Security deposit: $1,850. Pet deposit: $300. Landlord: Sunrise Property Management. Address: 789 Oak Street, Apt 204.

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

### Property Listing

**Input:**
> MLS #2025-45678 - 456 Maple Avenue. 3 bed, 2 bath single family home. 1,850 sq ft. Built 1995. List price: $425,000. Listed by: Coldwell Banker Realty. Agent: Michael Chen. Days on market: 14. Open house: Sunday, February 15, 2025.

**Output:**
```json
{
  "domain": "housing",
  "category": "search",
  "doctype": "listing",
  "vendor": "Coldwell Banker Realty",
  "date": "20250215",
  "subject": "456 maple avenue"
}
```

### Consulting Client Contract

**Input:**
> Professional Services Agreement between TechStart Inc. and Jane Smith Consulting LLC. Effective date: January 15, 2025. Scope: Software architecture review and recommendations. Compensation: $150/hour, not to exceed $15,000. Term: 3 months. Contact: Tom Wilson, CTO.

**Output:**
```json
{
  "domain": "career",
  "category": "clients",
  "doctype": "contract",
  "vendor": "TechStart Inc",
  "date": "20250115",
  "subject": "architecture consulting"
}
```

### Travel Trip Record

**Input:**
> Trip Confirmation - Hawaiian Airlines. Confirmation: HA7X2K9. Passenger: John Smith. Departing: San Francisco (SFO) to Honolulu (HNL), March 10, 2025, Flight HA21. Returning: March 17, 2025, Flight HA22. Hotel: Hilton Hawaiian Village, 7 nights.

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
