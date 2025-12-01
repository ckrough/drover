# WARP.md

This file provides guidance to WARP (warp.dev) when working with code in this repository.

## Project Overview

Drover is a document classification CLI that uses LLMs to analyze documents and suggest organized filesystem paths. It supports multiple AI providers (Ollama, OpenAI, Anthropic) through LangChain.

## Commands

```bash

# Create venv if needed
  if [[ ! -x .venv/bin/python ]]; then
    python3 -m venv .venv
  fi

# Activate venv
  source .venv/bin/activate

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

# Linting
ruff check src/

# Fix lint issues
ruff check src/ --fix
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
