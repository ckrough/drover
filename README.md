# Drover

Document classification CLI that herds files into organized folder structures.

Named after herding dogs that drove livestock — Drover uses LLMs to analyze documents and suggest consistent, policy-compliant filesystem paths and filenames.

## Installation

```bash
pip install -e ".[dev]"
```

## Usage

```bash
# Classify a single document
drover classify document.pdf --ai-provider ollama --ai-model llama3.1:latest

# Batch processing
drover classify *.pdf --batch
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run linter
ruff check src/
```
