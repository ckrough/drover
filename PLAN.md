# Plan: Classification System Improvements

Based on AI Engineer review feedback. Implementation prioritized by impact.

## Phase 1: Quick Wins (High Impact, Low Effort)

### 1.1 Fix Prompt Example Errors

**File:** `src/drover/prompts/classification.md`

| Example | Current Error | Fix |
|---------|---------------|-----|
| Medical Invoice (line 51-66) | doctype: "receipt" | Change to "invoice" |
| Tax Form W-2 (line 85-100) | doctype: "statement" | Change to "tax_form" |
| Property Deed (line 119-134) | vendor: "123 Main Street" | Change to "County Recorder" |
| Household Goods Receipt (line 153-168) | subject: "bedding and household items" (6 words) | Shorten to "bedding towels" |

### 1.2 Add Date Selection Priority Rule

**File:** `src/drover/prompts/classification.md`

Add to Important Guidelines section:
```markdown
- For the date, use this priority order:
  1. Transaction/service date (when the event occurred)
  2. Statement/issue date (when document was created)
  3. Due date (only if others unavailable)
```

### 1.3 Add Field Validation to JSON Parsing

**File:** `src/drover/classifier.py`

In `_parse_response()` method, add validation after parsing:
```python
required_fields = {"domain", "category", "doctype", "vendor", "date", "subject"}
missing = required_fields - set(parsed.keys())
if missing:
    raise LLMParseError(f"LLM response missing required fields: {missing}")
```

### 1.4 Remove Problematic Categories from Taxonomy

**File:** `src/drover/taxonomy/household.py`

Remove "receipts" and "statements" from financial categories (these are doctypes, not categories).

---

## Phase 2: Accuracy Improvements (Medium Effort)

### 2.1 Add Reasoning Step to Prompt

**File:** `src/drover/prompts/classification.md`

Add analysis process section:
```markdown
## Analysis Process

1. **Identify key entities**: Companies, people, amounts, dates mentioned
2. **Determine primary purpose**: Payment, record-keeping, legal agreement, reference
3. **Extract metadata**: Vendor (issuer), date (when it occurred), subject (what it's about)
4. **Classify**: Select domain, category, and document type from valid options
```

### 2.2 Add Domain Selection Guidelines

**File:** `src/drover/prompts/classification.md`

Add disambiguation rules:
```markdown
## Domain Selection Guidelines

When choosing between overlapping domains:
- **employment vs financial**: Use "employment" for job-related docs, "financial" for personal money
- **property vs housing**: Use "property" for owned property, "housing" for rentals and searches
- **medical vs insurance**: Use "medical" for health records, "insurance" for policy documents
```

### 2.3 Increase Temperature

**File:** `src/drover/classifier.py`

Change default temperature from 0.0 to 0.1 for more flexible reasoning.

### 2.4 Reduce Examples (Token Optimization)

**File:** `src/drover/prompts/classification.md`

Reduce from 17 examples to 8-10 strategically selected ones:
- Keep: Banking Statement, Medical Invoice, Tax Form, Property Deed, Utility Bill, Recipe
- Keep: Apartment Lease, Property Listing, Consulting Contract, Travel Trip (new examples)
- Remove: Redundant examples (Insurance Policy, Paystub, Tuition Invoice, Vehicle Title, Household Goods, Will/Estate, Home Improvement)

---

## Phase 3: Advanced Features (Higher Effort)

### 3.1 Store Raw Values in Normalization

**File:** `src/drover/models.py`

Add optional raw fields to RawClassification:
```python
class RawClassification(BaseModel):
    domain: str
    domain_raw: str | None = None
    category: str
    category_raw: str | None = None
    doctype: str
    doctype_raw: str | None = None
    # ... existing fields
```

### 3.2 Add Token Usage Monitoring

**File:** `src/drover/classifier.py`

Add warning for high token usage:
```python
if collect_metrics and debug_info.get("metrics"):
    total_tokens = debug_info["metrics"].get("total_tokens", 0)
    if total_tokens > 8000:
        logger.warning("high_token_usage", total_tokens=total_tokens)
```

### 3.3 Implement Hallucination Detection

**File:** `src/drover/classifier.py`

Add validation method to check if extracted values appear in document:
```python
def _validate_against_content(self, classification: dict, content: str) -> list[str]:
    """Check if extracted values appear in document content."""
    warnings = []
    vendor = classification.get("vendor", "")
    if vendor and vendor != "unknown" and vendor.lower() not in content.lower():
        warnings.append(f"vendor '{vendor}' not found in document")
    return warnings
```

### 3.4 Optimize Taxonomy Menu Format

**File:** `src/drover/taxonomy/base.py`

Update `to_prompt_menu()` to use compact format (estimated 200-300 token savings).

### 3.5 Add Taxonomy Versioning

**Files:** `src/drover/taxonomy/base.py`, `src/drover/models.py`

Add version tracking for taxonomy changes.

---

## Expected Outcomes

| Metric | Current | After Phase 1 | After Phase 2 | After Phase 3 |
|--------|---------|---------------|---------------|---------------|
| Token cost/request | ~3,500-7,000 | ~3,000-6,000 | ~2,000-4,000 | ~1,800-3,500 |
| Classification accuracy | Baseline | +10-15% | +20-25% | +25-30% |
| Error debuggability | Limited | Improved | Good | Excellent |

---

## Files to Modify

| File | Phases |
|------|--------|
| `src/drover/prompts/classification.md` | 1, 2 |
| `src/drover/classifier.py` | 1, 2, 3 |
| `src/drover/taxonomy/household.py` | 1 |
| `src/drover/taxonomy/base.py` | 3 |
| `src/drover/models.py` | 3 |
| `tests/test_classifier_parse.py` | 1 |
| `tests/test_taxonomy.py` | 1 |
