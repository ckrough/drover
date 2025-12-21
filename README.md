<p align="center">
  <img src="assets/drover-logo.png" alt="Drover logo" width="200">
</p>

<h1 align="center">Drover</h1>

<p align="center">
  <strong>AI-powered document classification that herds files into organized folders</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#quick-start">Quick Start</a> •
  <a href="#usage">Usage</a> •
  <a href="#configuration">Configuration</a> •
  <a href="#documentation">Documentation</a>
</p>

---

Drover uses LLMs to analyze documents and suggest consistent, policy-compliant filesystem paths and filenames. Named after herding dogs that drove livestock, Drover herds your scattered files into an organized folder structure.

## Features

- **Multi-Provider AI** — Works with Ollama (local), OpenAI, Anthropic, and OpenRouter
- **Intelligent Classification** — Categorizes documents by domain, category, and document type
- **Smart Sampling** — Adaptive page sampling for efficient processing of large documents
- **Taxonomy System** — Extensible controlled vocabularies with strict or fallback modes
- **NARA-Compliant Naming** — Generates standardized filenames: `{doctype}-{vendor}-{subject}-{date}.pdf`
- **macOS Tagging** — Apply classification as native filesystem tags
- **Batch Processing** — Classify multiple documents with JSONL output
- **Evaluation Framework** — Measure accuracy against ground truth datasets

## Quick Start

### Prerequisites

- Python 3.13+
- [Ollama](https://ollama.ai/) (for local inference) or API keys for cloud providers

### Installation

```bash
# Clone and install
git clone https://github.com/ckrough/drover.git
cd drover
pip install -e .

# Download required NLTK data (one-time)
python -c "import nltk; nltk.download('averaged_perceptron_tagger_eng'); nltk.download('punkt_tab')"
```

### Classify Your First Document

```bash
# Using local Ollama (default)
drover classify document.pdf

# Using OpenAI
export OPENAI_API_KEY="sk-..."
drover classify document.pdf --ai-provider openai --ai-model gpt-4o
```

## Usage

### Classify Command

Analyze documents and output suggested file paths:

```bash
drover classify invoice.pdf
drover classify *.pdf --batch                    # Multiple files, JSONL output
drover classify doc.pdf --metrics                # Include AI metrics
drover classify doc.pdf --log-level verbose      # Detailed logging
```

### Tag Command (macOS)

Classify and apply native filesystem tags:

```bash
drover tag document.pdf --dry-run                # Preview tags
drover tag document.pdf --tag-fields domain,vendor
drover tag --tag-mode replace document.pdf       # Replace existing tags
```

### Evaluate Command

Measure classification accuracy against ground truth:

```bash
drover evaluate eval/ground_truth.jsonl
drover evaluate eval/ground_truth.jsonl --output-format json
```

### Output Format

```json
{
  "original": "scan001.pdf",
  "suggested_path": "financial/banking/statement/statement-chase-checking-20240115.pdf",
  "domain": "financial",
  "category": "banking",
  "doctype": "statement",
  "vendor": "chase",
  "date": "20240115",
  "subject": "checking"
}
```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DROVER_AI_PROVIDER` | AI provider (ollama, openai, anthropic, openrouter) | `ollama` |
| `DROVER_AI_MODEL` | Model name | `llama3.2:latest` |
| `DROVER_TAXONOMY` | Classification taxonomy | `household` |
| `DROVER_NAMING_STYLE` | Filename policy | `nara` |
| `DROVER_SAMPLE_STRATEGY` | Page sampling (full, first_n, bookends, adaptive) | `adaptive` |
| `DROVER_LOG_LEVEL` | Logging verbosity (quiet, verbose, debug) | `quiet` |

### Config File

Drover searches for configuration in order: `--config PATH` → `drover.yaml` → `~/.config/drover/config.yaml`

```yaml
# drover.yaml
ai:
  provider: openai
  model: gpt-4o
  temperature: 0.0

taxonomy: household
taxonomy_mode: fallback
naming_style: nara
concurrency: 4
```

### AI Providers

| Provider | API Key Variable | Example Model |
|----------|------------------|---------------|
| Ollama | — (local) | `llama3.2:latest` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-20250514` |
| OpenRouter | `OPENROUTER_API_KEY` | `anthropic/claude-sonnet-4` |

## Supported File Formats

| Category | Extensions |
|----------|------------|
| PDF | `.pdf` |
| Images | `.png`, `.jpg`, `.jpeg`, `.gif`, `.bmp`, `.tiff`, `.tif` |
| Office | `.docx`, `.doc`, `.xlsx`, `.xls`, `.pptx`, `.ppt` |
| Text | `.txt`, `.md`, `.html`, `.htm`, `.csv`, `.tsv` |
| Other | `.eml`, `.epub`, `.odt`, `.rtf` |

## Architecture

Drover follows a pipeline architecture with extensible plugin systems:

```
[Document] → [Loader] → [Classifier] → [PathBuilder] → [Output]
                ↓             ↓              ↓
           [Sampling]   [Taxonomy]    [NamingPolicy]
```

**Tech Stack:**
- **CLI:** Click
- **LLM:** LangChain with structured output
- **Config:** Pydantic
- **Logging:** structlog

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Lint and format
ruff check src/ --fix && ruff format src/

# Security scan
bandit -r src/ -c pyproject.toml
```

## Documentation

- [Contributing Guide](CONTRIBUTING.md) — Development setup, architecture, and extension guides
- [ADR-001: Chain-of-Thought Prompting](docs/adr/001-chain-of-thought-prompting.md) — 7-step reasoning for accurate classification
- [ADR-002: Privacy-First Design](docs/adr/002-privacy-first-design.md) — Local-first, zero telemetry approach

## License

MIT
