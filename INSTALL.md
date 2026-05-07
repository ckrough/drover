# Install Drover

This guide installs the `drover` CLI on your system so you can run it from any directory. It is written for users who want to *use* drover. For development setup (editable installs, test suite, contributing), see `CONTRIBUTING.md`.

## Prerequisites

- **uv** (https://docs.astral.sh/uv/getting-started/installation/): manages drover's isolated Python environment, downloads the right Python version, and exposes `drover` on your `PATH`. No separate Python install needed.
- **Ollama** (optional, https://ollama.com/download): drover's default provider runs locally via Ollama. If you only plan to use a hosted provider (OpenAI, Anthropic, OpenRouter), you can skip Ollama and configure provider/model in `drover.yaml` or via `DROVER_*` environment variables. See `README.md` for configuration details.

## Install on macOS

The recommended install includes two optional extras:

| Extra | Purpose |
|-------|---------|
| `docling` | PDF / DOCX / HTML / image loader. Required: drover ships no other loader. |
| `ocr-mac` | Routes OCR through Apple's Vision framework (`ocrmac`). Without it, Docling falls back to `rapidocr` on the torch CPU backend, which is noticeably slower and uses Chinese-language model weights. |

Install directly from GitHub:

```bash
uv tool install "drover[docling,ocr-mac] @ git+https://github.com/ckrough/drover"
uv tool update-shell      # adds ~/.local/bin to PATH (idempotent, run once)
```

Restart your shell (or open a new terminal), then verify:

```bash
which drover              # should print /Users/<you>/.local/bin/drover
drover --help
```

## First run: download Docling models

Docling needs its layout and table-recognition weights cached locally before the first classification:

```bash
uvx --from docling docling-tools models download
```

This downloads to `~/.cache/docling/models/` (about 600 MB) and is shared across every Docling install on the machine, so it only needs to run once per user.

## Set up Ollama (skip if using a hosted provider)

Drover defaults to Ollama with `gemma4:latest`. To use that path, run Ollama and pull the model once:

```bash
ollama serve &            # or launch the Ollama.app menu-bar app
ollama pull gemma4:latest
```

## Verify the OCR backend

Run any PDF with verbose logging:

```bash
drover classify --log-level verbose path/to/document.pdf
```

In the output, look for:

```
Auto OCR model selected ocrmac with ...
```

If you see `rapidocr with torch` instead, the `ocr-mac` extra did not install. Reinstall:

```bash
uv tool install --reinstall "drover[docling,ocr-mac] @ git+https://github.com/ckrough/drover"
```

## Upgrading

```bash
uv tool upgrade drover
```

This pulls the latest commit from the same source you installed from. To pin to a specific version or tag:

```bash
uv tool install --reinstall \
  "drover[docling,ocr-mac] @ git+https://github.com/ckrough/drover@v0.1.0"
```

## Uninstalling

```bash
uv tool uninstall drover
```

This removes the tool's virtual environment and the `drover` shim from `~/.local/bin/`. Cached Docling models in `~/.cache/docling/` are left in place; remove them manually if drover was their only consumer.

## Linux

On Linux, install without the `ocr-mac` extra (it is gated to `darwin`):

```bash
uv tool install "drover[docling] @ git+https://github.com/ckrough/drover"
```

Docling will use `rapidocr`. For faster Linux OCR, also install `onnxruntime` so `rapidocr` runs on the ONNX backend instead of torch:

```bash
uv tool install --reinstall --with onnxruntime \
  "drover[docling] @ git+https://github.com/ckrough/drover"
```

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `command not found: drover` | `~/.local/bin` not on `PATH` | Run `uv tool update-shell`, then restart your shell |
| `docling is not installed` error on every file | Installed without the `docling` extra | Reinstall with `[docling,ocr-mac]` |
| Every file errors with `Docling models not found at ~/.cache/docling/models` | First-run model download was skipped | Run `uvx --from docling docling-tools models download` |
| Classify hangs for ~30 s, then errors | Ollama not running or `gemma4:latest` not pulled | `ollama serve` and `ollama pull gemma4:latest`, or switch provider in `drover.yaml` |
| Verbose log shows `rapidocr with torch` on macOS | `ocr-mac` extra missing | Reinstall with `[docling,ocr-mac]` |
