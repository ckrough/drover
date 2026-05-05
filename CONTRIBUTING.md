# Contributing to Drover

This guide covers development setup, architecture, and how to extend Drover.

## Development Setup

### Prerequisites

- Python 3.13.x
- [uv](https://docs.astral.sh/uv/) (package and environment manager)

### Environment Setup

Drover uses [uv](https://docs.astral.sh/uv/) for dependency management. `uv` creates and manages the project's virtual environment automatically; you do not need to create or activate `.venv` manually.

```bash
# Install uv (macOS / Linux)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Sync project dependencies (creates .venv and installs runtime + dev extras)
uv sync --all-extras
```

#### First-run setup: Docling models

The Docling loader requires model files (~500 MB) that must be downloaded once
before first use. Run this after `uv sync --all-extras`:

```bash
uv run docling-tools models download
```

Models are stored at `~/.cache/docling/models` and used offline on all
subsequent runs. If you skip this step, `DoclingLoader` raises a
`DocumentLoadError` with instructions rather than attempting a silent
network download at classification time.

`uv run <command>` executes commands inside the project environment without requiring activation. To enter a shell with the environment active, use `uv shell` or `source .venv/bin/activate`.

### Running Tests

```bash
# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_taxonomy.py

# Run a specific test
uv run pytest tests/test_taxonomy.py::TestHouseholdTaxonomy::test_canonical_domain_alias

# Run with coverage
uv run pytest --cov=src/drover --cov-report=term-missing
```

### Code Quality

```bash
# Lint and format
uv run ruff check src/ --fix && uv run ruff format src/

# Type checking
uv run mypy src/

# Security scan
uv run bandit -r src/ -f json --severity-level medium --confidence-level medium --quiet -c pyproject.toml
```

### Managing Dependencies

```bash
# Add a runtime dependency
uv add <package>

# Add a dev dependency
uv add --optional dev <package>

# Upgrade the lockfile
uv lock --upgrade
```

## Project Structure

```
src/drover/
├── __init__.py         # Package init, version definition
├── __main__.py         # Entry point for python -m drover
├── cli.py              # Click CLI commands (classify, tag, evaluate)
├── config.py           # Configuration management (Pydantic models)
├── loader.py           # DoclingLoader (sole loader; structure-aware with full-page OCR)
├── classifier.py       # LLM-based DocumentClassifier
├── path_builder.py     # PathBuilder - generates organized paths
├── models.py           # Data models (RawClassification, ClassificationResult)
├── service.py          # High-level service orchestration
├── metrics.py          # Classification metrics tracking (incl. cache metrics)
├── sampling.py         # Page sampling strategies
├── logging.py          # Structured logging configuration (structlog)
├── evaluation.py       # Classification evaluation framework
├── prompts/            # Prompt templates
│   └── classification.md
├── taxonomy/           # Taxonomy plugin system
│   ├── base.py         # BaseTaxonomy abstract class
│   ├── household.py    # HouseholdTaxonomy implementation
│   └── loader.py       # Taxonomy registry
├── naming/             # Naming policy plugin system
│   ├── base.py         # BaseNamingPolicy abstract class
│   ├── nara.py         # NARA-compliant naming
│   └── loader.py       # Naming policy registry
└── actions/            # File action implementations
    ├── base.py         # ActionPlan and ActionResult dataclasses
    ├── runner.py       # ActionRunner orchestration
    └── tag.py          # macOS filesystem tagging
```

## Architecture

### Core Pipeline Flow

```
1. CLI (cli.py)
   └── Entry point, orchestrates the pipeline

2. Loader (loader.py)
   └── DoclingLoader (sole loader; structure-aware with full-page OCR).
       Requires `uv sync --extra docling` and a one-time
       `uv run docling-tools models download` (~500 MB to
       ~/.cache/docling/models). Decision rationale: ADR-005, ADR-006.

3. DocumentClassifier (classifier.py)
   └── Sends content to LLM using structured output for reliable extraction

4. PathBuilder (path_builder.py)
   └── Generates {domain}/{category}/{doctype}/{filename} paths
```

### Plugin Systems

Drover uses three plugin systems for extensibility:

#### Taxonomies (`taxonomy/`)

Define controlled vocabularies for classification.

- `BaseTaxonomy` - Abstract base with canonical values + alias mappings
- `HouseholdTaxonomy` - Default taxonomy with domains (financial, medical, legal, etc.)
- Taxonomies normalize LLM outputs
- Modes: `strict` (reject unknown) or `fallback` (map to "other")

#### Naming Policies (`naming/`)

Define filename conventions.

- `BaseNamingPolicy` - Abstract base for character restrictions and format patterns
- `NARAPolicyNaming` - NARA-compliant format: `{doctype}-{vendor}-{subject}-{YYYYMMDD}.{ext}`

#### Actions (`actions/`)

Post-classification file operations.

- `ActionPlan` / `ActionResult` - Plan and result dataclasses
- `ActionRunner` - Orchestrates action execution with concurrency
- `TagAction` - macOS filesystem tagging via xattr

### Key Models (`models.py`)

```python
# LLM output before normalization
class RawClassification:
    domain: str
    category: str
    doctype: str
    vendor: str
    date: str      # YYYYMMDD format
    subject: str

# Final output with suggested path
class ClassificationResult:
    original: str
    suggested_path: str
    suggested_filename: str
    domain: str
    category: str
    doctype: str
    vendor: str
    date: str
    subject: str
    error: bool
    error_code: ErrorCode | None
    error_message: str | None
    metrics: dict | None

# Error response
class ClassificationErrorResult:
    original: str
    error: bool = True
    error_code: ErrorCode
    error_message: str
    metrics: dict | None
```

### Configuration (`config.py`)

Configuration uses Pydantic models with this precedence:

```
CLI options > config file > environment (DROVER_*) > defaults
```

Config locations searched:
1. `--config` path
2. `drover.yaml` in current directory
3. `~/.config/drover/config.yaml`

### Prompt Template

`src/drover/prompts/classification.md` uses YAML frontmatter with two placeholders:
- `{taxonomy_menu}` - Dynamically generated from taxonomy
- `{document_content}` - Extracted document text

## Extending Drover

### Adding a New Taxonomy

1. Create a class inheriting `BaseTaxonomy` in `taxonomy/`:

```python
# taxonomy/business.py
from typing import ClassVar
from drover.taxonomy.base import BaseTaxonomy

class BusinessTaxonomy(BaseTaxonomy):
    CANONICAL_DOMAINS: ClassVar[set[str]] = {
        "contracts",
        "finance",
        "hr",
        "legal",
        "operations",
    }

    CANONICAL_CATEGORIES: ClassVar[dict[str, set[str]]] = {
        "finance": {"accounting", "budgets", "invoices", "payroll"},
        "hr": {"benefits", "hiring", "policies", "reviews"},
        # ... more categories
    }

    CANONICAL_DOCTYPES: ClassVar[set[str]] = {
        "contract",
        "invoice",
        "memo",
        "policy",
        "report",
    }

    DOMAIN_ALIASES: ClassVar[dict[str, str]] = {
        "accounting": "finance",
        "human_resources": "hr",
    }

    CATEGORY_ALIASES: ClassVar[dict[tuple[str, str], str]] = {
        ("finance", "bills"): "invoices",
    }

    DOCTYPE_ALIASES: ClassVar[dict[str, str]] = {
        "bill": "invoice",
    }

    @property
    def name(self) -> str:
        return "business"
```

2. Register in `taxonomy/loader.py`:

```python
from drover.taxonomy.business import BusinessTaxonomy

_BUILTIN_TAXONOMIES: dict[str, type[BaseTaxonomy]] = {
    "household": HouseholdTaxonomy,
    "business": BusinessTaxonomy,  # Add here
}
```

### Adding a New Naming Policy

1. Create a class inheriting `BaseNamingPolicy` in `naming/`:

```python
# naming/simple.py
from drover.naming.base import BaseNamingPolicy, NamingConstraints

class SimpleNamingPolicy(BaseNamingPolicy):
    """Simple naming: {vendor}-{subject}.{ext}"""

    @property
    def name(self) -> str:
        return "simple"

    @property
    def constraints(self) -> NamingConstraints:
        return NamingConstraints(
            max_filename_length=100,
            max_component_length=30,
            allowed_chars_pattern=r"[a-z0-9_-]",
            word_separator="_",
            component_separator="-",
        )

    def format_filename(
        self,
        doctype: str,
        vendor: str,
        subject: str,
        date: str,
        extension: str,
    ) -> str:
        vendor_norm = self.normalize_vendor(vendor)
        subject_norm = self.normalize_component(subject)
        return f"{vendor_norm}-{subject_norm}.{extension}"
```

2. Register in `naming/loader.py`:

```python
from drover.naming.simple import SimpleNamingPolicy

_BUILTIN_POLICIES: dict[str, type[BaseNamingPolicy]] = {
    "nara": NARAPolicyNaming,
    "simple": SimpleNamingPolicy,  # Add here
}
```

### Adding a New Action

1. Create an action class implementing the `FileAction` protocol in `actions/`:

```python
# actions/rename.py
from pathlib import Path
from drover.actions.base import ActionPlan, ActionResult
from drover.models import ClassificationResult

class RenameAction:
    """Rename files based on classification."""

    def plan(self, file: Path, classification: ClassificationResult) -> ActionPlan:
        new_name = classification.suggested_filename
        return ActionPlan(
            file=file,
            action="rename",
            description=f"Rename to {new_name}",
            details={"new_name": new_name},
        )

    def execute(self, plan: ActionPlan) -> ActionResult:
        try:
            new_path = plan.file.parent / plan.details["new_name"]
            plan.file.rename(new_path)
            return ActionResult(
                file=plan.file,
                action=plan.action,
                success=True,
                details={"new_path": str(new_path)},
            )
        except Exception as e:
            return ActionResult(
                file=plan.file,
                action=plan.action,
                success=False,
                error=str(e),
            )
```

2. Export in `actions/__init__.py` and use with `ActionRunner`.

## Code Style

- **Line length:** 100 characters
- **Type hints:** Required on all public function signatures
- **Data containers:** Use Pydantic models or dataclasses
- **Imports:** stdlib → third-party → local (enforced by ruff)

## Testing

### Conventions

- Use pytest with pytest-asyncio (`asyncio_mode = "auto"`)
- **Never call real LLMs in unit tests** — mock at the classifier level
- Test names: `test_<function>_<scenario>_<expected>`

### Mocking Pattern

Test parsing logic directly without LLM invocation:

```python
def test_parse_response_direct_json() -> None:
    classifier = _make_classifier()  # uses dummy model
    result = classifier._parse_response('{"domain": "financial", ...}')
    assert result["domain"] == "financial"
```

### Coverage

Aim for >80% coverage on business logic. Run with:

```bash
pytest --cov=src/drover --cov-report=term-missing
```

## Common Gotchas

### Plugin Registration

When adding a taxonomy or naming policy, you **must** register it in the corresponding `loader.py`:
- Taxonomies: `taxonomy/loader.py` → `_BUILTIN_TAXONOMIES`
- Naming policies: `naming/loader.py` → `_BUILTIN_POLICIES`

### LLM Non-determinism

LLM outputs vary between runs. Always:
- Normalize through taxonomy
- Handle edge cases in `_parse_response()`
- Test with multiple variations of expected output

### JSON Parsing

LLMs may:
- Wrap JSON in markdown code blocks (`` ```json ... ``` ``)
- Add explanatory text before/after JSON
- Use `{{ }}` instead of `{ }`

The parser in `classifier.py` handles these, but be aware when debugging.

### Taxonomy Modes

- `strict`: Rejects unknown values (raises error)
- `fallback`: Maps unknown values to "other" category

Use fallback for production, strict for testing taxonomy completeness.

### Config Precedence

CLI options override config file, which overrides environment variables, which override defaults. Check all layers when debugging config issues.

### Async Considerations

- ClassificationService uses async for I/O-bound LLM calls
- Use `pytest-asyncio` with `asyncio_mode = "auto"`
- Tests can use `async def test_...()` directly

## LLM Integration Patterns

### Structured Output

The classifier uses LangChain's `with_structured_output()` for reliable JSON extraction:

```python
# classifier.py uses this pattern
llm_with_schema = self._get_llm().with_structured_output(RawClassification)
classification = await llm_with_schema.ainvoke(message, config=invoke_config)
```

This eliminates brittle regex-based JSON parsing and provides automatic Pydantic validation.

### Prompt Caching (Anthropic)

For Anthropic models, prompt caching is enabled automatically via the `anthropic-beta: prompt-caching-2024-07-31` header. The taxonomy menu (~2000 tokens) is cached, reducing costs by up to 90% on subsequent requests.

Cache metrics are tracked in `ClassificationMetrics`:
- `cache_creation_input_tokens`: Tokens written to cache (first request)
- `cache_read_input_tokens`: Tokens read from cache (subsequent requests)

### Streaming Classification

For interactive use cases, `classify_streaming()` provides real-time token output:

```python
async def on_token(token: str) -> None:
    print(token, end="", flush=True)

result = await classifier.classify_streaming(content, on_token=on_token)
```

## Evaluation Framework

The `evaluation.py` module enables systematic measurement of classification accuracy:

```python
from drover.evaluation import ClassificationEvaluator

evaluator = ClassificationEvaluator(ground_truth_path="eval/ground_truth/synthetic.jsonl")
results = await evaluator.evaluate(classifier)
print(f"Domain accuracy: {results.domain_accuracy:.1%}")
```

### Ground Truth Format

JSONL file with expected classifications:

```jsonl
{"filename": "bank.pdf", "domain": "financial", "category": "banking", "doctype": "statement"}
{"filename": "bill.pdf", "domain": "financial", "category": "utilities", "doctype": "bill"}
```

### Running Evaluations

```bash
drover evaluate eval/ground_truth/synthetic.jsonl --ai-model gpt-4o --output-format json
```

To track accuracy over time across models, loaders, and corpora, open `eval/dashboard.html` in a browser. The dashboard reads from `eval/dashboard_data.json`, which is committed and survives deletion of per-run directories. After adding new runs, regenerate the summary with:

```bash
uv run python scripts/build_eval_dashboard.py
```

## Architecture Decision Records

Design decisions are documented in `docs/adr/`:

- [ADR-001](docs/adr/001-chain-of-thought-prompting.md): Chain-of-thought prompting strategy
- [ADR-002](docs/adr/002-privacy-first-design.md): Privacy-first design principles
- [ADR-003](docs/adr/003-nli-classifier-roadmap.md): Zero-shot NLI classifier roadmap (superseded by ADR-004)
- [ADR-004](docs/adr/004-local-llm-as-primary-local-path.md): Local LLM (Ollama gemma4) as the primary local classification path
- [ADR-005](docs/adr/005-docling-evaluation.md): Docling with full-page OCR as the default PDF loader
