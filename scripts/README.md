# Drover Scripts

Operational and analysis scripts that complement the `drover` CLI. None of these scripts are required for normal classification, tagging, or evaluation use of the CLI itself; they exist for batch operations, eval orchestration, dashboard maintenance, and taxonomy refinement.

All scripts run via `uv` from the repo root:

```bash
uv run python scripts/<script>.py [args]
```

Agent Note: sandbox blocks `127.0.0.1:11434`, so any invocation that reaches the local Ollama instance needs `dangerouslyDisableSandbox: true` or a non-sandboxed shell.

## Eval and benchmarking

### `run_eval_experiments.py`

Multi-model classification experiment runner. Reads a YAML experiment definition (model matrix + document set + ground truth), runs each combination, and writes one JSONL per experiment to `eval/results/`. Supports `run`, `report`, and `validate` subcommands. Use this when comparing several models or prompt variants against the same ground-truth corpus.

```bash
uv run python scripts/run_eval_experiments.py run eval/example_experiment.yaml -v
uv run python scripts/run_eval_experiments.py report eval/results/example-model-comparison-*.jsonl
```

### `generate_eval_samples.py`

Synthetic eval-corpus generator. Picks `(domain, category, doctype)` triples from `HouseholdTaxonomy`, asks Claude to write realistic prose for each, renders as PDF, and appends a row to `eval/ground_truth/synthetic.jsonl`. Used to grow the synthetic corpus when ground-truth coverage gaps appear.

```bash
uv run python scripts/generate_eval_samples.py --count 30 --concurrency 5
```

### `build_eval_dashboard.py`

Regenerator for `eval/dashboard_data.json` and the inline data block in `eval/dashboard.html`. Idempotent: existing entries are preserved, new runs in `eval/runs/` are appended, runs are sorted chronologically. Strips per-document records before writing so the committed summary is PII-safe. Runs whose directory name starts with `baseline-` are tagged with `baseline: true` so the static chart can clip to runs at-or-after the most recent baseline.

Per `CLAUDE.md` note 14, both `dashboard.html` and `dashboard_data.json` are regenerator-managed. Run this script after adding any run to `eval/runs/`. Never edit either file by hand.

```bash
uv run python scripts/build_eval_dashboard.py
```

### `build_eval_charts.py`

Regenerator for `eval/charts/accuracy-over-time.png`. Reads `eval/dashboard_data.json`, clips to runs at-or-after the most recent run tagged `baseline: true`, and renders one line per accuracy metric. X-axis labels are short commit hashes (matching the interactive dashboard's `fmtCommit`). Run after `build_eval_dashboard.py` updates the JSON.

```bash
uv run python scripts/build_eval_charts.py
```

## Taxonomy analysis

### `discover_taxonomy_terms.py`

Captures raw LLM suggestions in fallback mode before normalization. Use this when investigating new domains, categories, or doctypes that the LLM proposes but the canonical taxonomy doesn't yet cover. Emits Python or JSON suitable for refining `HouseholdTaxonomy` aliases.

```bash
uv run python scripts/discover_taxonomy_terms.py documents/*.pdf
uv run python scripts/discover_taxonomy_terms.py --sample 100 --seed 42 ~/Documents
```

### `collect_classification_tuples.py`

PII-safe corpus aggregator for taxonomy-improvement work. Walks a directory, classifies each document in fallback mode, and writes one JSON file containing raw and canonical `(domain, category, doctype)` tuple counts, drift records (raw term outside the canonical set), term frequencies, and aggregate vendor and date counters. Filenames and document text never leave the harvester. Used to drive the Round 1 through Round 4 demotion arc and to validate post-merge drift redistribution against the personal archive.

```bash
uv run python scripts/collect_classification_tuples.py \
  ~/Documents/personal-archive \
  --ai-provider ollama --ai-model gemma4:latest \
  --output eval/runs/$(date +%Y%m%d-%H%M%S)/realworld-tuples.json --verbose
```

## Operational

The recursive classify-rename-tag flow is now part of the main CLI as `drover organize`. Use that subcommand instead of a script wrapper:

```bash
drover organize ~/Documents --dest ~/Documents/filed --dry-run --report -
drover organize ~/Inbox/scan.pdf --dest ~/Documents/filed --tag-fields category,doctype
```

See the top-level `README.md` and `CLAUDE.md` for the full flag matrix.
