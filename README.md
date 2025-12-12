# Drover

Document classification CLI that herds files into organized folder structures.

Named after herding dogs that drove livestock — Drover uses LLMs to analyze documents and suggest consistent, policy-compliant filesystem paths and filenames.

## Installation

```bash
pip install -e ".[dev]"
```

### NLTK Data

Drover disables automatic NLTK downloads for privacy (to prevent network calls). You must pre-download the required NLTK packages once:

```python
import nltk
nltk.download('averaged_perceptron_tagger_eng')
nltk.download('punkt_tab')
```

## Usage

```bash
# Classify a single document (using local Ollama)
drover classify document.pdf --ai-provider ollama --ai-model llama3.1:latest

# Using OpenRouter (requires OPENROUTER_API_KEY env var)
export OPENROUTER_API_KEY="sk-or-..."
drover classify document.pdf --ai-provider openrouter --ai-model anthropic/claude-3.5-sonnet

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
