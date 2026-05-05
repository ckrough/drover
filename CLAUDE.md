# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Drover is a document classification CLI that uses LLMs to analyze documents and suggest organized filesystem paths. It supports multiple AI providers (Ollama, OpenAI, Anthropic, OpenRouter) through LangChain. The default local path is Ollama with `gemma4:latest`, which extracts the full classification (domain, category, doctype, vendor, date, subject) in a single structured-output call.

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed architecture, code style, and extension guides.

## Python Environment Setup

### Package Manager
- **ALWAYS** use `uv` for dependency management and command execution
- **NEVER** install packages globally with `pip`, and do not invoke `pip` directly in this project
- Use `uv run <command>` to execute project commands without manually activating the venv
- Use `uv add <package>` (or `uv add --optional dev <package>`) to introduce new dependencies — this updates `pyproject.toml` and `uv.lock` together

### Python Version
- Use Python 3.13.x (pinned in `pyproject.toml`)
- Check version: `uv run python --version`

### Before Running Any Python Code
```bash
# Sync runtime + dev dependencies into .venv (uv manages it for you)
uv sync --all-extras
```

## Project Structure

```
src/drover/
├── __init__.py         # Package init, version definition
├── __main__.py         # Entry point for python -m drover
├── cli.py              # Click CLI commands (classify, tag, evaluate)
├── config.py           # Configuration management (Pydantic models)
├── loader.py           # DocumentLoader - text extraction from documents
├── classifier.py       # LLM-based DocumentClassifier (uses structured output)
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
    └── tag.py          # macOS filesystem tagging (TagAction, TagMode)
```

## Eval Layout

- `eval/samples/synthetic/` — 80 synthetic PDFs (committed)
- `eval/samples/real-world/` — 14 real-world PDFs (gitignored; PII)
- `eval/ground_truth/synthetic.jsonl` — synthetic labels (committed)
- `eval/ground_truth/real-world.jsonl` — real-world labels (gitignored; PII in filenames/vendors/dates)
- `eval/runs/<timestamp>/results.md` — committed when free of PII
- `eval/runs/<timestamp>/*.json` — per-doc dumps (gitignored)
- `eval/dashboard.html` and `eval/dashboard_data.json` — regenerator-managed via `scripts/build_eval_dashboard.py`; aggregates only, no per-doc PII

## Commands

```bash
# Install with dev dependencies
uv sync --all-extras

# Run CLI - classify command (LLM-based)
uv run drover classify document.pdf --ai-provider ollama --ai-model gemma4:latest

# Run CLI - tag command (macOS only)
uv run drover tag document.pdf --dry-run
uv run drover tag document.pdf --tag-fields domain,category --tag-mode replace

# Run CLI - evaluate command
uv run drover evaluate --ground-truth eval/ground_truth/synthetic.jsonl --ai-model gpt-4o

# Run all tests
uv run pytest

# Run a single test file
uv run pytest tests/test_taxonomy.py

# Run a specific test
uv run pytest tests/test_taxonomy.py::TestHouseholdTaxonomy::test_canonical_domain_alias

# Lint and format
uv run ruff check src/ --fix && uv run ruff format src/

# Type checking
uv run mypy src/

# Security scan
uv run bandit -r src/ -f json --severity-level medium --confidence-level medium --quiet -c pyproject.toml
```

## Architecture Quick Reference

### Core Pipeline Flow
1. **CLI** (`cli.py`) → Entry point, orchestrates the pipeline
2. **DocumentLoader** (`loader.py`) → Extracts text from documents with sampling strategies
3. **DocumentClassifier** (`classifier.py`) → Uses LangChain's `with_structured_output()` for reliable extraction
4. **PathBuilder** (`path_builder.py`) → Generates `{domain}/{category}/{doctype}/{filename}` paths

### Plugin Systems
- **Taxonomies** (`taxonomy/`): Controlled vocabularies. Register new ones in `taxonomy/loader.py`
- **Naming Policies** (`naming/`): Filename conventions. Register new ones in `naming/loader.py`
- **Actions** (`actions/`): Post-classification operations like tagging

### Key Models (`models.py`)
- `RawClassification` → LLM output: domain, category, doctype, vendor, date, subject
- `ClassificationResult` → Final output with suggested_path
- `ClassificationErrorResult` → Error response with error_code

### Configuration (`config.py`)
Precedence: CLI options > config file > environment (DROVER_*) > defaults

Config locations: `drover.yaml`, `~/.config/drover/config.yaml`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DROVER_AI_PROVIDER` | AI provider (ollama, openai, anthropic, openrouter) | `ollama` |
| `DROVER_AI_MODEL` | Model name | `gemma4:latest` |
| `DROVER_AI_TEMPERATURE` | LLM temperature (0.0-2.0) | `0.0` |
| `DROVER_AI_MAX_TOKENS` | Maximum tokens in LLM response | `1000` |
| `DROVER_AI_TIMEOUT` | Request timeout in seconds | `60` |
| `DROVER_AI_MAX_RETRIES` | Maximum retry attempts | `3` |
| `DROVER_AI_RETRY_MIN_WAIT` | Minimum wait between retries (seconds) | `2.0` |
| `DROVER_AI_RETRY_MAX_WAIT` | Maximum wait between retries (seconds) | `10.0` |
| `OPENAI_API_KEY` | API key for OpenAI (required when provider=openai) | — |
| `ANTHROPIC_API_KEY` | API key for Anthropic (required when provider=anthropic) | — |
| `OPENROUTER_API_KEY` | API key for OpenRouter (required when provider=openrouter) | — |
| `DROVER_TAXONOMY` | Taxonomy to use | `household` |
| `DROVER_TAXONOMY_MODE` | Validation mode (strict, fallback) | `fallback` |
| `DROVER_NAMING_STYLE` | Naming policy | `nara` |
| `DROVER_SAMPLE_STRATEGY` | Page sampling strategy | `adaptive` |
| `DROVER_MAX_PAGES` | Max pages to sample | `10` |
| `DROVER_PROMPT` | Custom prompt template file path | — |
| `DROVER_LOG_LEVEL` | Logging (quiet, verbose, debug) | `quiet` |
| `DROVER_ON_ERROR` | Error handling (fail, continue, skip) | `fail` |
| `DROVER_CONCURRENCY` | Parallel processing | `1` |
| `DROVER_DEBUG_DIR` | Directory for debug outputs | `./debug` |
| `debug_structure` | Dump `DoclingDocument` JSON to `debug_dir` for inspection (config-file / CLI flag only; no env-var hookup yet) | `false` |

## Testing

- pytest with pytest-asyncio (`asyncio_mode = "auto"`); do NOT add `@pytest.mark.asyncio` decorators (redundant noise)
- For tests requiring the optional Docling extra, use `pytest.importorskip("docling")` at module top
- **Never call real LLMs in unit tests** — mock at the classifier level
- Test parsing logic directly without LLM invocation:

```python
def test_parse_response_direct_json() -> None:
    classifier = _make_classifier()  # uses dummy model
    result = classifier._parse_response('{"domain": "financial", ...}')
    assert result["domain"] == "financial"
```

## Important Notes

1. **Register new plugins:** When adding a taxonomy or naming policy, register it in the corresponding `loader.py`

2. **LLM non-determinism:** LLM outputs vary between runs. Always normalize through taxonomy and handle edge cases in `_parse_response()`

3. **JSON parsing:** LLMs may wrap JSON in markdown code blocks or add explanatory text. The parser handles these.

4. **Taxonomy modes:** `strict` rejects unknown values; `fallback` maps to "other" category

5. **Config precedence:** CLI > config file > environment > defaults

6. **Async:** ClassificationService is async. Use `pytest-asyncio` for tests.

7. **Structured output:** Classifier uses `with_structured_output()` for reliable JSON extraction. Falls back to regex parsing if structured output fails.

8. **Prompt caching:** Anthropic models use prompt caching for the taxonomy menu (~2000 tokens). Check `cache_read_input_tokens` in metrics.

9. **Streaming:** Use `classify_streaming()` for real-time token output in interactive contexts.

10. **Evaluation:** Use `drover evaluate` to measure accuracy against ground truth. See `evaluation.py` for the framework.

11. **ADRs:** Architectural decisions are documented in `docs/adr/`. ADR-004 standardized on the local LLM (Ollama gemma4) as the primary local path. ADR-005 sets Docling with full-page OCR as the default PDF loader; ADR-006 supersedes the ADR-005 fallback path and makes Docling the sole loader (the `unstructured` backend was removed, the `--loader` flag is gone, and `_SUPPORTED_EXTENSIONS` was reduced to Docling's officially-supported set). First-time Docling setup requires `uv sync --extra docling` and `uv run docling-tools models download`. Beads issue: `prof-m78`.

    **Taxonomy (Round 4):** Canonical doctypes are plural (LCGFT genre/form alignment): folders use the plural (`receipts/`, `invoices/`, `agreements/`); filenames use the singular instance form (`receipt-...pdf`). `BaseTaxonomy.singular_form()` and `HouseholdTaxonomy.DOCTYPE_SINGULAR` mediate the split, applied by `PathBuilder` before the naming policy formats the filename. Cross-references to LCGFT and schema.org live in `docs/taxonomy/external-mapping.md`; design rationale in `docs/taxonomy/design-rationale.md`. The form-vs-subject structural rule (categories name subjects, doctypes name forms) is enforced by `tests/test_taxonomy.py::test_no_canonical_category_is_also_canonical_doctype`.

12. **Docling first-run failure signature:** If every doc errors with `Docling models not found at ~/.cache/docling/models`, run `uv run docling-tools models download` once. The error is actionable but easy to miss in batch eval logs.

13. **Sandbox + Ollama:** The Bash sandbox blocks localhost (`127.0.0.1:11434`). Run any command that calls the Ollama provider with `dangerouslyDisableSandbox: true` (drover classify/evaluate, ollama list, etc.).

14. **Eval dashboard:** `eval/dashboard.html` and `eval/dashboard_data.json` are both regenerator-managed by `scripts/build_eval_dashboard.py`. After adding a run to `eval/runs/`, run the script; never edit either file by hand.

15. **Ollama structured output (gemma):** Use `with_structured_output(method="json_mode", include_raw=True)` for the Ollama provider. The default `json_schema` (constrained decoding) produces tool-call fallback on non-tool-trained models like gemma when prompts are long. `num_predict` is bumped to ≥ 3072 on the Ollama path for the same reason.
