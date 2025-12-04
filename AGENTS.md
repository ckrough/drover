# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Drover is a document classification CLI that uses LLMs to analyze documents and suggest organized filesystem paths. It supports multiple AI providers (Ollama, OpenAI, Anthropic) through LangChain.

**Python Version:** 3.11.3+

## Commands

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run CLI
drover classify document.pdf --ai-provider ollama --ai-model llama3.2:latest

# Run all tests
pytest

# Run a single test file
pytest tests/test_taxonomy.py

# Run a specific test
pytest tests/test_taxonomy.py::TestHouseholdTaxonomy::test_canonical_domain_alias

# Lint and format
ruff check src/ --fix && ruff format src/

# Security scan
bandit -r src/ -f json --severity-level medium --confidence-level medium --quiet -c pyproject.toml
```

## Architecture

### Core Pipeline Flow
1. **CLI** (`cli.py`) → Entry point, orchestrates the pipeline
2. **DocumentLoader** (`loader.py`) → Extracts text from PDFs/images via LangChain loaders with sampling strategies
3. **DocumentClassifier** (`classifier.py`) → Sends content to LLM with taxonomy-constrained prompts
4. **PathBuilder** (`path_builder.py`) → Generates `{domain}/{category}/{doctype}/{filename}` paths using naming policies

### Plugin Systems

**Taxonomies** (`taxonomy/`) - Define controlled vocabularies for classification:
- `BaseTaxonomy` → Abstract base with canonical values + alias mappings
- `HouseholdTaxonomy` → Default taxonomy with domains (financial, medical, legal, etc.)
- Taxonomies normalize LLM outputs and can run in `strict` (reject unknown) or `fallback` (map to "other") modes

**Naming Policies** (`naming/`) - Define filename conventions:
- `BaseNamingPolicy` → Abstract base for character restrictions and format patterns
- `NARAPolicyNaming` → NARA-compliant format: `{doctype}-{vendor}-{subject}-{YYYYMMDD}.{ext}`

### Key Models (`models.py`)
- `RawClassification` → LLM output: domain, category, doctype, vendor, date, subject
- `ClassificationResult` → Final output with suggested_path
- `ClassificationError` → Error response with error_code

### Configuration (`config.py`)
Precedence: CLI options > config file > environment (DROVER_*) > defaults

Config locations searched: `drover.yaml`, `~/.config/drover/config.yaml`

### Prompt Template
`src/drover/prompts/classification.md` uses YAML frontmatter + `{taxonomy_menu}` and `{document_content}` placeholders.

## Extending the System

**Add a new taxonomy:**
1. Create class inheriting `BaseTaxonomy` in `taxonomy/`
2. Define `CANONICAL_DOMAINS`, `CANONICAL_CATEGORIES`, `CANONICAL_DOCTYPES`, and alias dicts
3. Register in `taxonomy/loader.py` `_BUILTIN_TAXONOMIES`

**Add a new naming policy:**
1. Create class inheriting `BaseNamingPolicy` in `naming/`
2. Implement `format_filename()` method
3. Register in `naming/loader.py`

## Code Style

- **Line length:** 100 characters
- **Type hints:** Required on all public function signatures
- **Data containers:** Use Pydantic models or dataclasses
- **Imports:** stdlib → third-party → local (enforced by ruff)

## Testing

- pytest with pytest-asyncio (`asyncio_mode = "auto"`)
- **Never call real LLMs in unit tests** — mock at the classifier level
- Test parsing logic directly without LLM invocation:

```python
def test_parse_response_direct_json() -> None:
    classifier = _make_classifier()  # uses dummy model
    result = classifier._parse_response('{"domain": "financial", ...}')
    assert result["domain"] == "financial"
```

## Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DROVER_AI_PROVIDER` | AI provider (ollama, openai, anthropic) | `ollama` |
| `DROVER_AI_MODEL` | Model name | `llama3.2:latest` |
| `DROVER_ENCODER_ENABLED` | Enable local encoder classifier | `true` |
| `DROVER_ENCODER_MODEL` | Sentence-transformer model | `all-MiniLM-L6-v2` |
| `DROVER_ENCODER_DEVICE` | Device (cpu, cuda, mps) | `mps` |
| `DROVER_TAXONOMY` | Taxonomy to use | `household` |
| `DROVER_TAXONOMY_MODE` | Validation mode (strict, fallback) | `fallback` |
| `DROVER_NAMING_STYLE` | Naming policy | `nara` |
| `DROVER_SAMPLE_STRATEGY` | Page sampling strategy | `adaptive` |
| `DROVER_MAX_PAGES` | Max pages to sample | `10` |
| `DROVER_LOG_LEVEL` | Logging (quiet, verbose, debug) | `quiet` |
| `DROVER_ON_ERROR` | Error handling (fail, continue, skip) | `fail` |
| `DROVER_CONCURRENCY` | Parallel processing | `1` |
| `DROVER_DEBUG_DIR` | Directory for debug outputs | `./debug` |

## Common Gotchas

1. **Register new plugins:** When adding a taxonomy or naming policy, you MUST register it in the corresponding `loader.py` (`taxonomy/loader.py` or `naming/loader.py`)

2. **LLM non-determinism:** LLM outputs vary between runs. Always normalize through taxonomy and handle edge cases in `_parse_response()`

3. **JSON parsing:** LLMs may wrap JSON in markdown code blocks, add explanatory text, or use `{{ }}` instead of `{ }`. The parser handles these, but be aware when debugging.

4. **Taxonomy modes:**
   - `strict`: Rejects unknown values (raises error)
   - `fallback`: Maps unknown values to "other" category

5. **Encoder vs LLM classifiers:**
   - `DocumentClassifier`: Uses LLM API calls (slower, more accurate)
   - `EncoderClassifier`: Local embeddings (faster, no API cost)
   - `HybridClassifier`: Encoder for taxonomy, LLM for metadata extraction

6. **Config precedence:** CLI options override config file, which overrides environment variables, which override defaults. Check all layers when debugging config issues.

7. **Async considerations:** Some classifiers are async. Use `pytest-asyncio` and `asyncio_mode = "auto"` in pytest config.
