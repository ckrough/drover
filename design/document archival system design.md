# Document archival system design

Personal and household financial documents require decades-long retention in a system that remains intelligible without reprocessing. This comprehensive archival system synthesizes industry standards from ARMA International's recordkeeping principles, IRS retention requirements, NARA file naming standards, and ISO 15489 records management specifications to create a clean, broad-categorical structure optimized for long-term personal document management.

## Directory taxonomy structure

The four-level hierarchy follows the pattern: **Domain → Category → Vendor → Document**, using broad classifications that accommodate diverse document types without granular subdivisions. This structure aligns with professional document management principles emphasizing sustainability, accessibility, and consistent organization over decades.

### Level 1: Domain (19 primary domains)

**career**
Professional development and work-related documents outside of current employment. Includes job applications, client work, consulting, resumes, presentations, and professional development materials.

**education**
Academic records including transcripts, certifications, financial aid documentation, and educational correspondence.

**employment**
Current and past employment documentation including compensation records, benefits information, performance reviews, and workplace correspondence.

**financial**
Core financial instruments and accounts including banking, investments, credit, and retirement accounts. Encompasses all monetary transactions, statements, taxes, and account-related documentation.

**food**
Meal planning, recipes, and food-related reference materials.

**government**
Federal, state, and local government correspondence and documentation not fitting other specific categories.

**household**
General household management including emergency preparedness, home network documentation, maintenance schedules, and household vehicles.

**housing**
Real estate search, rental properties, property listings, and housing-related reference materials for properties you don't currently own.

**insurance**
All insurance policies and related documentation across auto, home, life, health, and umbrella coverage. Organized by insurance type.

**legal**
Contracts, estate planning documents, court records, legal correspondence, and identity documents including birth certificates, wills, trusts, and powers of attorney.

**lifestyle**
Personal goals, interests, travel planning, trip documentation, and volunteering records.

**medical**
Healthcare records, billing, insurance claims, prescriptions, lab results, dental, vision, mental health, and provider documentation. Separated from general insurance due to unique retention requirements and frequent access needs.

**other**
Uncategorized documents that don't fit established domains.

**personal**
Identity documents, personal correspondence, memberships, and travel documentation.

**pets**
Pet-related documentation including medical records and registration.

**property**
Real property ownership documentation for properties you own, including mortgage, maintenance, improvements, HOA, and rental management.

**reference**
General reference materials including manuals and topical guides not specific to other domains.

**utilities**
Utility service documentation including electric, gas, water, internet, phone, and trash services.

**vehicles**
Vehicle ownership documentation including purchase records, registration, maintenance, insurance, and loans.

### Level 2: Category (by domain)

**career categories:**
- applications (job applications)
- clients (client work and relationships)
- consulting (consulting engagements)
- documentation (professional documentation)
- employers (employer-related records)
- interviewing (interview materials)
- job_search (job search activities)
- leadership (leadership materials)
- meetings (meeting notes and agendas)
- performance_reviews (performance documentation)
- presentations (presentation materials)
- professional_development (training and development)
- reference (professional references)
- resumes (resumes and CVs)
- expenses (receipts and invoices for professional expenses, conferences, certifications)
- agreements (consulting contracts, NDA agreements, professional service agreements)
- other

**education categories:**
- transcripts (academic transcripts)
- certifications (professional certifications)
- correspondence (educational correspondence)
- financial_aid (financial aid documentation)
- expenses (receipts and invoices for tuition, books, supplies, course fees)
- agreements (enrollment agreements, student loan agreements)
- other

**employment categories:**
- compensation (salary, bonuses, paystubs)
- benefits (health, retirement, other benefits)
- performance (performance reviews)
- correspondence (workplace correspondence)
- other

**financial categories:**
- banking (checking, savings, money market accounts)
- credit (credit cards, lines of credit)
- investments (brokerage, mutual funds, stocks, bonds)
- retirement (401k, IRA, pension, Social Security)
- taxes (tax returns, W-2s, 1099s, deduction records)
- loans (mortgages, auto loans, student loans, personal loans)
- other

**food categories:**
- meal_plans (meal planning documents)
- recipes (recipe collections)
- reference (food-related reference)
- other

**government categories:**
- federal (federal government documents)
- state (state government documents)
- local (local government documents)
- correspondence (government correspondence)
- other

**household categories:**
- emergency_preparedness (emergency plans and supplies)
- home_network (network documentation)
- maintenance (household maintenance schedules)
- vehicles (household vehicle documentation)
- expenses (receipts and invoices for household supplies, repairs)
- agreements (service contracts, warranties, subscription agreements)
- other

**housing categories:**
- properties (property documentation)
- reference (housing reference materials)
- rentals (rental property documentation)
- search (property search materials)
- other

**insurance categories:**
- auto (vehicle insurance)
- home (homeowners/renters insurance)
- life (life insurance)
- health (health insurance policies)
- umbrella (umbrella liability)
- claims (insurance claims)
- other

**legal categories:**
- contracts (legal contracts)
- estate_planning (wills, trusts, beneficiary designations)
- court (court documents)
- correspondence (legal correspondence)
- identification (identity documents)
- reference (legal reference materials)
- other

**lifestyle categories:**
- goals (personal goals)
- interests (hobbies and interests)
- planning (life planning)
- travel (travel planning)
- trips (trip documentation)
- volunteering (volunteer activities)
- expenses (receipts and invoices for hobby supplies, travel expenses)
- agreements (membership contracts, club agreements, subscription services)
- other

**medical categories:**
- records (medical history, test results)
- billing (medical bills, EOBs)
- insurance_claims (insurance claim documentation)
- prescriptions (medication records)
- lab_results (laboratory test results)
- dental (dental records)
- mental_health (mental health records)
- primary_care (primary care documentation)
- specialists (specialist documentation)
- vision (vision care records)
- immunizations (vaccination records)
- reference (medical reference materials)
- other

**other categories:**
- uncategorized (documents that don't fit elsewhere)

**personal categories:**
- identity (birth certificates, passports, Social Security cards)
- correspondence (personal correspondence)
- memberships (club and organization memberships)
- travel (travel documents)
- other

**pets categories:**
- medical (pet medical records)
- registration (pet registration documents)
- expenses (receipts and invoices for pet supplies, food, toys)
- agreements (adoption papers, boarding contracts, service agreements)
- other

**property categories:**
- mortgage (mortgage documentation)
- maintenance (property maintenance records)
- improvements (home improvement documentation)
- hoa (HOA documentation)
- rental (rental property management)
- properties (property records)
- rentals (rental documentation)
- search (property search materials)
- reference (property reference materials)
- expenses (receipts and invoices for property-related purchases)
- agreements (service contracts, warranties, HOA agreements)
- other

**reference categories:**
- manuals (product manuals)
- topics (topical reference materials)
- other

**utilities categories:**
- electric (electricity service)
- gas (natural gas service)
- water (water service)
- internet (internet service)
- phone (phone service)
- trash (waste management)
- other

**vehicles categories:**
- purchase (vehicle purchase documentation)
- registration (vehicle registration)
- maintenance (vehicle maintenance records)
- insurance (vehicle insurance)
- loans (vehicle loans)
- reference (vehicle reference materials)
- expenses (receipts and invoices for vehicle-related purchases, accessories)
- agreements (service contracts, warranties, extended warranties)
- other

### Level 3: Vendor

This level identifies the specific institution, company, or entity associated with the document. **Vendor names are frozen at the time of archival**—corporate name changes, mergers, or rebranding are not reflected in historical documents to maintain consistency and prevent reprocessing.

**Naming conventions for vendors:**
- Use commonly recognized names, not legal corporate entities
- Remove punctuation and special characters
- Use underscores for multi-word names: "Bank_of_America" not "BankofAmerica"
- Abbreviate when standard abbreviation exists: "BCBS" for Blue Cross Blue Shield
- For individuals (doctors, lawyers): lastname_firstname format

**Examples by category:**

*Banking:* Chase, Wells_Fargo, Bank_of_America, Ally_Bank, Local_Credit_Union

*Investment:* Vanguard, Fidelity, Charles_Schwab, TD_Ameritrade, Robinhood

*Insurance:* State_Farm, Geico, Aetna, BCBS, United_Healthcare

*Real Estate:* Property address as identifier (123_Main_St, 456_Oak_Ave)

*Retailers:* Amazon, Best_Buy, Home_Depot, Target, Walmart

*Utilities:* Duke_Energy, Comcast, Verizon, City_Water, Waste_Management

*Healthcare:* Smith_John_MD, City_Hospital, CVS_Pharmacy, Quest_Diagnostics

### Level 4: Document (files)

Individual documents stored with standardized naming convention (detailed in next section). This level contains the actual PDF, image, or document files with embedded metadata in the filename.

### Complete taxonomy examples

```
career/
├── resumes/
│   └── resume-self-software_engineer-20250101.pdf
├── presentations/
│   └── presentation-acme_corp-quarterly_review-20250315.pdf
└── clients/
    └── Acme_Corp/
        └── contract-acme_corp-consulting-20250201.pdf

education/
├── transcripts/
│   └── record-state_university-transcript-20200515.pdf
└── certifications/
    └── certificate-aws-solutions_architect-20240601.pdf

employment/
├── compensation/
│   ├── Acme_Corp/
│   │   ├── paystub-acme_corp-salary-20250115.pdf
│   │   └── paystub-acme_corp-salary-20250131.pdf
│   └── tax_form-employer-w2-20250131.pdf
└── benefits/
    └── policy-acme_corp-401k_plan-20250101.pdf

financial/
├── banking/
│   ├── Chase/
│   │   ├── statement-chase-checking-20250131.pdf
│   │   ├── statement-chase-checking-20250228.pdf
│   │   └── receipt-chase-wiretransfer-20250315.pdf
│   └── Ally_Bank/
│       ├── statement-allybank-savings-20250131.pdf
│       └── statement-allybank-savings-20250228.pdf
├── investments/
│   └── Vanguard/
│       ├── statement-vanguard-ira-20250331-q1.pdf
│       └── receipt-vanguard-purchase-20250215.pdf
├── credit/
│   └── Amex/
│       ├── statement-amex-bluecash-20250131.pdf
│       └── receipt-amex-annual_fee-20250101.pdf
└── taxes/
    ├── 2024/
    │   ├── tax_return-irs-form1040-20250415.pdf
    │   └── notice-irs-refund_issued-20250520.pdf
    └── 2023/
        └── tax_return-irs-form1040-20240415.pdf

food/
├── recipes/
│   └── recipe-grandma-chocolate_cake-20200101.pdf
└── meal_plans/
    └── meal_plan-self-weekly-20250106.pdf

government/
├── federal/
│   └── notice-irs-audit_letter-20250301.pdf
├── state/
│   └── license-dmv-drivers-20230710.pdf
└── local/
    └── permit-city-fence_install-20240515.pdf

household/
├── emergency_preparedness/
│   └── guide-fema-emergency_plan-20240101.pdf
├── home_network/
│   └── manual-ubiquiti-network_setup-20230815.pdf
└── maintenance/
    └── record-self-maintenance_schedule-20250101.pdf

housing/
├── search/
│   └── listing-zillow-456_oak_ave-20250201.pdf
└── rentals/
    └── lease-landlord-apartment-20240601.pdf

insurance/
├── health/
│   └── BCBS/
│       ├── policy-bcbs-family_plan-20250101.pdf
│       └── receipt-bcbs-premium-20250401.pdf
├── home/
│   └── State_Farm/
│       └── policy-statefarm-homeowners-20250101.pdf
├── auto/
│   └── State_Farm/
│       └── policy-statefarm-auto-20250601.pdf
└── claims/
    └── report-statefarm-auto_accident-20241210.pdf

legal/
├── identification/
│   ├── birth_certificate-vitals-smith_john-19800101.pdf
│   └── passport-state_dept-smith_john-20200301.pdf
├── estate_planning/
│   ├── will-attorney_jones-smith_family-20230915.pdf
│   └── trust-attorney_jones-revocable_living-20230915.pdf
└── contracts/
    └── agreement-landlord-lease-20240101.pdf

lifestyle/
├── travel/
│   └── itinerary-delta-hawaii_trip-20250615.pdf
├── trips/
│   └── booking_confirmation-marriott-hawaii-20250615.pdf
└── goals/
    └── journal-self-annual_goals-20250101.pdf

medical/
├── billing/
│   ├── City_Hospital/
│   │   ├── invoice-city_hosp-surgery-20250110.pdf
│   │   └── receipt-city_hosp-payment-20250201.pdf
│   └── CVS_Pharmacy/
│       └── receipt-cvs-prescription-20250305.pdf
├── records/
│   └── Smith_John_MD/
│       └── report-smith_md-annual_physical-20250220.pdf
├── lab_results/
│   └── report-quest_diagnostics-bloodwork-20250115.pdf
├── prescriptions/
│   └── record-cvs-medications-20250301.pdf
└── immunizations/
    └── immunization_record-cdc-covid_vaccine-20240315.pdf

personal/
├── identity/
│   └── social_security_card-ssa-smith_john-19800101.pdf
├── memberships/
│   └── certificate-costco-membership-20250101.pdf
└── travel/
    └── id_card-tsa-precheck-20230601.pdf

pets/
├── medical/
│   └── vaccination_record-vet-dog_max-20250201.pdf
└── registration/
    └── license-city-dog_max-20250101.pdf

property/
├── mortgage/
│   └── 123_Main_St/
│       ├── deed-123main-purchase-19950815.pdf
│       └── statement-wells_fargo-mortgage-20250101.pdf
├── improvements/
│   └── 123_Main_St/
│       ├── invoice-acme_roofing-replacement-20231020.pdf
│       └── receipt-lowes-kitchen_reno-20240305.pdf
├── maintenance/
│   └── 123_Main_St/
│       └── inspection_report-home_inspector-annual-20250301.pdf
└── hoa/
    └── 123_Main_St/
        └── hoa_statement-oak_ridge_hoa-quarterly-20250101.pdf

reference/
├── manuals/
│   └── manual-samsung-tv-20231125.pdf
└── topics/
    └── guide-irs-tax_deductions-20250101.pdf

utilities/
├── electric/
│   └── Duke_Energy/
│       └── invoice-duke_energy-electric-20250115.pdf
├── internet/
│   └── Comcast/
│       └── invoice-comcast-internet-20250201.pdf
└── water/
    └── City_Water/
        └── invoice-city_water-utilities-20250110.pdf

vehicles/
├── purchase/
│   └── 2022_Honda_Accord/
│       └── title-honda-purchase-20220612.pdf
├── maintenance/
│   └── 2022_Honda_Accord/
│       ├── receipt-honda_dealer-maintenance-20250201.pdf
│       └── invoice-jiffy_lube-oil_change-20250415.pdf
├── registration/
│   └── 2022_Honda_Accord/
│       └── license-dmv-registration-20250101.pdf
└── insurance/
    └── 2022_Honda_Accord/
        └── policy-statefarm-auto-20250601.pdf
```

## File naming convention

The standardized naming scheme ensures each filename is self-describing, sortable, and remains intelligible decades later without folder context. This convention synthesizes ARMA International principles with ISO 8601 date standards and NARA guidelines for federal records.

### Standard format

**Pattern:** `doctype-vendor-subject-YYYYMMDD.ext`

**Components (in fixed order):**

1. **Document type** (required): The direct purpose/nature of the document
2. **Vendor** (required): Entity that issued or is associated with the document
3. **Subject** (optional): Brief descriptor of purpose or content
4. **Date** (required): Effective or transaction date in ISO 8601 format (YYYYMMDD)
5. **Extension** (required): File type (.pdf, .jpg, .png)

### Component specifications

**Document type (doctype)**
Describes what the document IS, not what it's used for. Limited controlled vocabulary ensures consistency:

*Primary types:*
- **statement** - Periodic account summaries (bank, credit card, investment)
- **invoice** - Bill requesting payment
- **receipt** - Proof of payment for goods or services
- **contract** - Formal legal contract
- **agreement** - Legal contract or binding arrangement
- **letter** - Formal correspondence
- **notice** - Official communication from institution
- **form** - Official form (W-2, 1099, 1098)
- **application** - Application documents
- **policy** - Insurance coverage contract or terms
- **certificate** - Official verification document (birth, death, marriage)
- **report** - Medical test results, inspection reports, appraisals
- **record** - General record documentation
- **bill** - Bill for services
- **estimate** - Cost estimate
- **quote** - Price quote
- **warranty** - Product warranty documentation
- **manual** - Product or service manual
- **guide** - How-to or instructional guide
- **tax_return** - Tax return filing (1040, etc.)
- **tax_form** - Tax-related form (W-2, 1099, etc.)
- **deed** - Real estate ownership transfer document
- **title** - Legal ownership document (property, vehicle)
- **license** - Official authorization document
- **permit** - Official permit
- **recipe** - Cooking recipe
- **meal_plan** - Meal planning document
- **resume** - Resume or CV
- **cover_letter** - Job application cover letter
- **portfolio** - Work portfolio
- **presentation** - Presentation materials
- **reference_letter** - Letter of reference
- **immunization_record** - Vaccination records
- **referral** - Medical or professional referral
- **inspection_report** - Property or vehicle inspection
- **will** - Testament document
- **trust** - Legal trust document
- **power_of_attorney** - Power of attorney document
- **passport** - Travel document
- **birth_certificate** - Birth certificate
- **social_security_card** - Social Security card
- **itinerary** - Travel itinerary
- **booking_confirmation** - Reservation confirmation
- **journal** - Personal journal entry
- **vaccination_record** - Vaccination documentation
- **adoption_papers** - Adoption documentation
- **id_card** - Identification card
- **paystub** - Pay statement
- **lease** - Rental lease agreement
- **listing** - Property listing
- **offer** - Purchase offer
- **closing_statement** - Real estate closing documents
- **hoa_statement** - HOA statement or dues
- **other** - Other document types

**Vendor (entity)**
Institution, company, or person associated with the document. Apply consistent formatting:
- Remove spaces: use underscores for multi-word names
- Use common name, not legal corporate name
- Abbreviate when widely recognized (BCBS, IRS, DMV)
- For individuals: lastname_firstname or lastname only for brevity
- No punctuation or special characters
- Lowercase preferred for consistency

**Subject (descriptor)**
Brief, meaningful description using 1-3 words:
- Underscore for multi-word subjects: "kitchen_reno" not "kitchenreno"
- Account type for statements: "checking," "savings," "ira"
- Procedure/service for medical: "physical," "xray," "surgery"
- Purpose for receipts: "donation," "tuition," "maintenance"
- Product category for purchases: "laptop," "furniture," "tools"
- Keep concise: under 20 characters when possible

**Date (YYYYMMDD)**
ISO 8601 basic format without separators:
- Eight digits: year (4) + month (2) + day (2)
- No hyphens or slashes for filename brevity
- Use effective date, not document creation date
- For statements: last day of statement period
- For receipts/invoices: transaction date
- For policies: policy effective date
- For multi-year documents: use start year
- Unknown specific dates: use YYYY0000, YYYYMM00, or best approximation

**Extension**
Standard file formats for long-term preservation:
- **.pdf** - Preferred for documents (use PDF/A when possible)
- **.jpg** - Photographs, scanned images (use sparingly; TIFF or PNG better for archival)
- **.png** - Graphics requiring transparency
- **.tiff** - Archival-quality scans (lossless compression)

### Character restrictions

Following NARA Bulletin 2015-04 standards:
- **Permitted:** Lowercase a-z, numbers 0-9, hyphen (-), underscore (_)
- **Prohibited:** Spaces, periods (except before extension), special characters (/ \ : * ? " < > | # $ % & @ !)
- **One period only:** Immediately before file extension
- **Maximum length:** 32 characters (excluding extension) to ensure cross-platform compatibility
- **Case:** Lowercase throughout for consistency (case-sensitive systems treat "File.pdf" and "file.pdf" as different)

### Naming convention examples by document type

**Banking statements**
```
statement-chase-checking-20250131.pdf
statement-chase-savings-20250131.pdf
statement-allybank-moneymarket-20250228.pdf
```

**Credit card statements**
```
statement-amex-bluecash-20250115.pdf
statement-chase-sapphire-20250201.pdf
statement-discover-cashback-20250310.pdf
```

**Investment statements**
```
statement-vanguard-ira-20250331-q1.pdf
statement-fidelity-401k-20241231-annual.pdf
confirmation-schwab-purchase-20250215.pdf
confirmation-robinhood-sale-20250301.pdf
```

**Receipts (retail purchases)**
```
receipt-bestbuy-laptop-20240615.pdf
receipt-homedepot-lumber-20240720.pdf
receipt-amazon-furniture-20240805.pdf
receipt-target-groceries-20241115.pdf
```

**Receipts (services)**
```
receipt-jiffy_lube-oil_change-20250115.pdf
receipt-acme_plumbing-repair-20250203.pdf
receipt-smiths_lawn-mowing-20250615.pdf
```

**Receipts (charitable)**
```
receipt-red_cross-donation-20241225.pdf
receipt-alma_mater-annual_fund-20240630.pdf
receipt-goodwill-clothing-20241201.pdf
```

**Invoices**
```
invoice-duke_energy-electric-20250115.pdf
invoice-comcast-internet-20250201.pdf
invoice-city_water-utilities-20250110.pdf
invoice-acme_roofing-replacement-20231020.pdf
```

**Insurance policies**
```
policy-statefarm-homeowners-20250101.pdf
policy-statefarm-auto-20250601.pdf
policy-aetna-health_family-20250101.pdf
policy-northwestern-life_term-20200315.pdf
```

**Insurance claims and EOBs**
```
eob-bcbs-emergency_room-20250320.pdf
eob-aetna-surgery-20250115.pdf
claim-statefarm-auto_accident-20241210.pdf
```

**Property documents**
```
deed-123main-purchase-19950815.pdf
title-honda-2022_accord-20220612.pdf
appraisal-123main-refinance-20201105.pdf
inspection-123main-termite-20240508.pdf
```

**Tax documents**
```
return-irs-form1040-20250415.pdf
return-state-income-20250415.pdf
form-employer-w2-20250131.pdf
form-vanguard-1099div-20250215.pdf
notice-irs-refund_issued-20250520.pdf
```

**Medical records**
```
report-smith_md-annual_physical-20250220.pdf
report-city_hosp-xray_results-20250115.pdf
invoice-city_hosp-surgery-20250110.pdf
receipt-cvs-prescription-20250305.pdf
```

**Legal documents**
```
certificate-vitals-birth_smith_john-19800101.pdf
certificate-vitals-marriage-20050615.pdf
passport-state_dept-smith_john-20200301.pdf
license-dmv-drivers-20230710.pdf
will-attorney_jones-smith_john-20230915.pdf
trust-attorney_jones-revocable-20230915.pdf
agreement-employer-employment-20200101.pdf
```

**Warranties and manuals**
```
warranty-ge-dishwasher-20240310.pdf
warranty-samsung-tv-20231125.pdf
manual-honda-2022_accord-20220612.pdf
```

### Handling edge cases

**Multiple documents same day, same vendor:**
Add sequential suffix before extension:
```
receipt-homedepot-paint-20240720-1.pdf
receipt-homedepot-lumber-20240720-2.pdf
receipt-homedepot-hardware-20240720-3.pdf
```

**Multi-page scanned documents:**
Use sequential page numbers:
```
statement-chase-checking-20250131-p1.pdf
statement-chase-checking-20250131-p2.pdf
statement-chase-checking-20250131-p3.pdf
```
Or consolidate pages into single PDF (preferred).

**Date ranges (quarterly/annual statements):**
Use end date of period, optionally add period indicator:
```
statement-vanguard-ira-20250331-q1.pdf
statement-401k-employer-20241231-annual.pdf
```

**Unknown or approximate dates:**
Use partial dates:
```
certificate-vitals-birth-19800000.pdf (year only known)
receipt-vendor-purchase-198505.pdf (month known, day unknown)
```

**Amended or corrected documents:**
Add revision indicator:
```
return-irs-form1040-20250415.pdf (original)
return-irs-form1040x-20250815-amended.pdf (amended return)
```

**Documents without clear vendor:**
Use generic descriptor:
```
receipt-garage_sale-furniture-20240615.pdf
invoice-contractor-deck_repair-20240720.pdf
receipt-individual-lawn_mower-20240510.pdf
```

## Design rationale and industry standards

### Broad categorical structure

The 19-domain taxonomy reflects ARMA International's principle that **meaningful categories reduce decision fatigue and filing errors** while improving long-term sustainability. The expanded domain structure separates distinct life areas (career vs. employment, property vs. housing, vehicles as standalone) for clearer document placement.

**Key advantages:**
- **Clear boundaries:** Each document has obvious primary location with domain specialization
- **Life-stage coverage:** Domains cover career development, education, pets, lifestyle, and more
- **Future-proof:** Broad categories within domains absorb new document types
- **Low maintenance:** Minimal restructuring needed over decades
- **Family-friendly:** Others can navigate system without extensive documentation

### Document type as primary classifier

Organizing by **direct purpose** (what the document IS) rather than **indirect purpose** (what it's USED for) aligns with professional archival principles:

**Direct purpose:** "This is a RECEIPT from Home Depot"
**Indirect purpose:** "This is a TAX DEDUCTION for home office expenses"

**Rationale from records management theory:**
1. **Single correct location:** Each document has one unambiguous category (receipt), not multiple possible categories (tax, home office, office supplies, deductions)
2. **Temporal stability:** Purpose remains constant even if use changes (receipt remains receipt even if tax laws change deductibility)
3. **Retrieval efficiency:** Known document type enables faster location than reconstructing past purposes
4. **Multi-purpose flexibility:** Single document serves multiple needs without duplication (medical receipt is both healthcare record AND tax deduction, filed once under medical expenses)

### Vendor-level organization

Grouping documents by **vendor/institution** at level 3 reflects how people naturally remember and search for documents: "I need my Chase bank statement" or "Where's that Home Depot receipt?"

This aligns with user-centered information architecture principles:
- **Mental models:** Matches how people think about their documents
- **Chronological grouping:** All Chase statements together in date order
- **Relationship tracking:** Easy to see complete history with each vendor
- **Frozen naming:** Vendor names don't change with corporate rebranding, preventing need to reorganize historical documents

### ISO 8601 date format (YYYYMMDD)

The eight-digit date format without separators follows international archival standards:

**Standards compliance:**
- **ISO 8601:2004/2019** - International date representation standard
- **NARA Bulletin 2015-04** - Federal records file naming
- **ARMA International** - Recordkeeping best practices

**Technical advantages:**
- **Alphanumeric sorting equals chronological sorting:** Files automatically organize by date
- **Cross-platform compatibility:** Works on Windows, macOS, Linux, cloud storage
- **Fixed length:** Enables parsing and validation
- **Unambiguous:** Eliminates confusion between US (MM/DD/YYYY) and European (DD/MM/YYYY) formats
- **No special characters:** Hyphens and slashes problematic in filenames across systems

**Position justification:**
Date appears last (not first) because:
1. Document type provides strongest categorical identifier
2. Vendor provides secondary grouping
3. Within vendor folders, chronological sorting occurs naturally
4. Allows future migration to database systems where date becomes sortable field

### Character restrictions

Limiting characters to alphanumeric plus hyphen/underscore follows NARA federal records standards:

**Prohibited characters cause technical issues:**
- Spaces → Break command-line operations, create ugly URLs
- Slashes (/ \) → Path separators in operating systems
- Colons (:) → Drive designation (Windows), special meaning (macOS)
- Asterisks/question marks (* ?) → Wildcards in file operations
- Quotes (" ') → String delimiters in programming
- Special symbols → Various system-level meanings

**32-character limit rationale:**
- **Path length constraints:** Maximum 255 characters for full path (folder structure + filename)
- **Display compatibility:** Longer names truncate in file listings
- **Future-proofing:** Stricter limits ensure compatibility with legacy systems if needed
- **Usability:** Forces conciseness and meaningful abbreviation

### File format recommendations

**PDF preferred for documents:** Following NARA and Library of Congress digital preservation guidelines:
- **PDF/A** (PDF for Archive) - ISO 19005 standard for long-term preservation
- **Self-contained:** Fonts and formatting embedded
- **Universal compatibility:** Readable on any platform
- **OCR capability:** Text searchable after scanning
- **Security:** Encryption and password protection available

**TIFF for archival scans:** Professional standard for high-quality preservation:
- **Lossless compression:** No quality degradation
- **High resolution:** Captures fine detail
- **Industry standard:** Libraries and archives use TIFF for master copies
- **Metadata support:** Extensive technical metadata embedding

**Avoid proprietary formats:** Microsoft Office formats (.docx, .xlsx) acceptable for active documents but should be converted to PDF for archival to prevent dependency on specific software versions.

### Retention alignment

The taxonomy structure supports IRS and professional retention standards:

**7-year standard:** Most tax-related financial documents
- Banking, investment, credit statements
- Receipts supporting deductions
- Insurance policies and claims

**Indefinite retention:** Legal and property documents
- Birth certificates, passports, Social Security cards
- Property deeds and titles
- Wills, trusts, estate documents
- Tax returns themselves (supporting docs can be purged after 7 years)

**Property-related:** Until disposition + 7 years
- Home improvement receipts (affect cost basis)
- Investment purchase confirmations (determine capital gains)
- Vehicle maintenance records

The directory structure facilitates **batch deletion** when retention periods expire: entire vendor folders or year subfolders can be removed without sorting individual files.

## Implementation guidance

### Getting started

**Phase 1: System setup**
1. Create top-level domain folders (career, education, employment, financial, etc.)
2. Add second-level category folders within each domain
3. Document your naming convention in a README.txt file in the root directory
4. Set up cloud storage with encryption (Google Drive, Dropbox, OneDrive with Cryptomator)
5. Establish 3-2-1 backup: 3 copies, 2 media types, 1 offsite

**Phase 2: Historical document migration (Weeks 2-4)**
1. Start with permanent records (Legal domain) - most critical, typically smallest volume
2. Gather all existing documents by domain
3. Scan paper documents to PDF using OCR software
4. Rename files following naming convention
5. File chronologically within vendor folders
6. Shred paper after verification (except originals of birth certificates, deeds, titles, passports)

**Phase 3: Ongoing maintenance**
1. **Weekly:** Process new documents - scan, rename, file within 7 days of receipt
2. **Monthly:** Reconcile statements, verify all documents filed correctly
3. **Annually (each January):** Review prior year, ensure completeness, apply retention policy
4. **Every 3-5 years:** Verify backups, update storage media, check file format sustainability

### Scanning workflow

**Equipment:** Document scanner with automatic document feeder (ADF) and OCR capability
- Recommended: Fujitsu ScanSnap, Brother ADS series, Epson WorkForce
- Alternative: Smartphone scanning app (Adobe Scan, Microsoft Lens) for occasional documents

**Settings:**
- **Resolution:** 300 DPI minimum (600 DPI for small text)
- **Color mode:** Grayscale for text documents (reduces file size), color for images
- **Format:** PDF with OCR (searchable text)
- **Compression:** Medium (balances file size and quality)

**Process:**
1. Remove staples and paperclips
2. Scan to PDF with OCR
3. Verify legibility and completeness
4. Apply naming convention immediately
5. File in appropriate directory location
6. Shred original (unless permanent record requiring physical original)

### Search and retrieval

**Digital search methods:**
1. **Folder navigation:** Browse directory structure when you know general category and vendor
2. **Filename search:** Use operating system search for vendor name or date range
3. **Full-text search:** OCR-enabled PDFs allow searching document contents
4. **Metadata tags:** Advanced users can apply tags in file properties for additional filtering

**Search examples:**
- Find all Chase documents: Search filenames for "chase"
- Find 2024 tax documents: Navigate to 4_Tax/Supporting_Docs/2024/
- Find Home Depot receipts: Navigate to 1_Financial/Receipts/Home_Depot/ or search "receipt-homedepot"
- Find all insurance policies: Navigate to 3_Insurance/ and search filenames for "policy"

### Backup and security

**3-2-1 backup rule:**
- **3 copies** of every important document
- **2 different storage types** (cloud + external drive)
- **1 offsite copy** (cloud storage or external drive in safe location)

**Security measures:**
1. **Encryption:** Use encrypted cloud storage or add encryption layer (Cryptomator, Boxcryptor)
2. **Access control:** Password-protect devices and cloud accounts
3. **Multi-factor authentication:** Enable on all cloud storage accounts
4. **Secure deletion:** Use secure shredding for physical documents with sensitive information
5. **Regular verification:** Test restore procedures annually

**Physical storage:**
- Fireproof/waterproof safe for permanent records physical originals
- Safe deposit box for irreplaceable documents (consider access limitations)
- Climate-controlled environment (avoid attics, basements prone to temperature extremes)

### System documentation

Create **README.txt** file in root directory containing:

```
PERSONAL DOCUMENT ARCHIVE SYSTEM
Created: [Date]
Last Updated: [Date]

DIRECTORY STRUCTURE:
4 levels: Domain > Category > Vendor > Document
- Level 1: 19 domains (career, education, employment, financial, food, government, household, housing, insurance, legal, lifestyle, medical, other, personal, pets, property, reference, utilities, vehicles)
- Level 2: Functional categories within each domain
- Level 3: Specific vendors/institutions
- Level 4: Individual document files

FILE NAMING CONVENTION:
Pattern: doctype-vendor-subject-YYYYMMDD.ext

Components:
- doctype: Type of document (receipt, invoice, statement, policy, etc.)
- vendor: Institution or company name (lowercase, underscores for spaces)
- subject: Brief descriptor (optional, 1-3 words)
- date: ISO 8601 format YYYYMMDD (effective date, not creation date)
- ext: File extension (.pdf preferred)

Examples:
- statement-chase-checking-20250131.pdf
- receipt-homedepot-lumber-20240720.pdf
- policy-statefarm-homeowners-20250101.pdf

RETENTION POLICY:
- 7 years: Financial statements, receipts, tax supporting documents
- Indefinite: Legal documents, property records (until sale + 7 years), tax returns
- Active: Insurance policies while in force, loan documents until satisfied

BACKUP STRATEGY:
- Primary: [Cloud service name]
- Backup 1: [External drive location]
- Backup 2: [Second cloud service or offsite drive]

VENDOR NAME POLICY:
Vendor names frozen at document date - do not update for corporate name changes

SPECIAL NOTES:
[Add household-specific information: family members covered, account details location, etc.]
```

### Common scenarios and solutions

**Scenario 1: Receipt could go multiple places**
*Example: Medical receipt that's also a tax deduction*
- **Solution:** File in primary functional location (6_Medical/Expenses/Provider_Name/)
- **Alternative:** If primarily kept for tax purposes, file in 4_Tax/Supporting_Docs/[Year]/ with filename: receipt-provider-medical_expense-YYYYMMDD.pdf
- **Digital advantage:** Use tags or keep single file with cross-referencing notes

**Scenario 2: Vendor changes name**
*Example: TD Ameritrade becomes part of Charles Schwab*
- **Solution:** Keep existing folder "TD_Ameritrade" for historical documents; create new "Schwab" folder for new documents
- **Rationale:** Maintains historical accuracy; vendor name reflects who issued the document
- **Note in documentation:** "TD Ameritrade acquired by Schwab [date]; documents remain under original vendor name"

**Scenario 3: Unknown or generic vendor**
*Example: Receipt from garage sale, or informal contractor*
- **Solution:** Use generic descriptors: "garage_sale," "individual," "contractor_[name]"
- **Filename:** receipt-garage_sale-lawn_mower-20240615.pdf or invoice-contractor_smith-deck_repair-20240720.pdf

**Scenario 4: Multi-purpose document**
*Example: Home improvement receipt affects property cost basis AND potential tax deduction*
- **Solution:** File in 2_Property/Real_Estate/[Address]/ (primary purpose: property record affecting cost basis)
- **Filename:** receipt-homedepot-kitchen_reno-20240305.pdf clearly indicates it's a receipt and can be found when needed for taxes
- **Note:** Avoid duplicating files; single authoritative location with clear naming makes document discoverable for any purpose

**Scenario 5: Ongoing service with many small receipts**
*Example: Monthly utility bills*
- **Solution:** Determine if bills have long-term value
- **Keep if:** Used for tax deductions (home office), property ownership records, or proof of residence
- **Discard after 1 year if:** Routine payments with no special purpose
- **File location:** 1_Financial/Utilities/[Vendor]/ or vendor-specific folder like 2_Property/Real_Estate/[Address]/Utilities/

## Conclusion

This document archival system synthesizes decades of professional records management standards into a practical framework for personal financial documents. By prioritizing broad categorical groupings, standardized naming conventions, and long-term sustainability, the system ensures documents remain accessible and intelligible for decades without reprocessing.

The four-level taxonomy balances organizational depth with simplicity, while the controlled-vocabulary naming convention provides self-describing filenames that work independently of folder context. Together, these elements create a clean, maintainable system that serves households through decades of accumulating financial records while supporting regulatory retention requirements and facilitating efficient retrieval when documents are needed.

Implementation success depends on three factors: **consistent application** of naming rules, **regular maintenance** routines for processing new documents, and **thorough documentation** so the system remains understandable to future users. Start simply with core domains, establish weekly filing habits, and the system will scale naturally as your document collection grows.