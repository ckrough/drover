# ADR-001: Chain-of-Thought Prompting Strategy

## Status
Accepted

## Context
Document classification requires nuanced reasoning. A simple prompt like "classify this document" often produces inconsistent results, especially for documents that could belong to multiple categories (e.g., a bank statement used for tax purposes).

We needed a prompting strategy that:
1. Improves classification accuracy
2. Produces consistent, reproducible results
3. Provides transparency into the model's reasoning
4. Handles edge cases gracefully

## Decision
Implement a 7-step chain-of-thought (CoT) reasoning process embedded directly in the prompt template (`prompts/classification.md`).

### The 7-Step Process:
1. **Extract Key Information** - Identify organizations, dates, document structure
2. **Evaluate Dates by Priority** - Apply consistent date selection rules
3. **Determine Document Type** - Identify what kind of document this is
4. **Analyze Potential Categories** - Consider multiple plausible options
5. **Determine the Domain** - Ask "What is this document fundamentally about?"
6. **Extract Vendor** - Identify the primary organization
7. **Synthesize Subject** - Create a brief, meaningful description

### Key Design Decisions:
- **Explicit reasoning tags**: Output wrapped in `<classification_analysis>` tags separates reasoning from final JSON
- **Domain selection rules**: Explicit guidance to classify by "fundamental purpose, NOT transactional use"
- **Priority-based date selection**: Clear hierarchy (document date > statement date > transaction date)
- **Subject clarity**: Instructions to avoid confusing form with content

## Consequences

### Positive
- **Higher accuracy**: CoT reasoning significantly improves classification consistency
- **Debuggability**: Captured reasoning in debug output shows why decisions were made
- **Prompt versioning**: CoT steps can be iteratively improved based on failure analysis
- **Transfer learning**: New taxonomy categories can include domain-specific reasoning

### Negative
- **Higher token usage**: CoT reasoning adds ~200 tokens per request
- **Increased latency**: More tokens = longer inference time
- **Parsing complexity**: Must handle both reasoning tags and JSON output

### Mitigations
- Structured output (`with_structured_output()`) simplifies parsing
- Prompt caching (Anthropic) reduces cost of repeated taxonomy menu
- Reasoning is optional - can be disabled for latency-sensitive use cases

## Evidence
Testing with household documents showed:
- Domain accuracy improved from ~75% to ~92% with CoT
- Misclassification patterns shifted from "wrong domain" to "edge cases" (acceptable)
- User feedback: CoT reasoning output is valuable for understanding/correcting errors

## Related
- `prompts/classification.md` - Prompt template with CoT steps
- `test_classifier_parse.py::test_parse_response_classification_analysis_tags` - Tests for CoT parsing
- `classifier.py:_parse_response()` - CoT tag extraction (handles `<classification_analysis>` tags)
