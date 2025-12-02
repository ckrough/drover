---
name: document_classification
version: "1.0"
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
  "date": "01/31/2025",
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
  "date": "January 10, 2025",
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
  "date": "January 1, 2025",
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
  "date": "January 31, 2025",
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
  "date": "December 1, 2024",
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
  "date": "March 5, 2025",
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
  "date": "01/15/2025",
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
  "date": "02/10/2025",
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
  "date": "January 20, 2025",
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
  "date": "February 5, 2025",
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
  "date": "December 15, 2024",
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
  "date": "March 1, 2025",
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
  "vendor_raw": "King Arthur Baking",
  "date_raw": "11/18/22",
  "subject_raw": "cranberry-orange babka"
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

## Examples

