# Scripts directory: agent guidance

For human-readable descriptions of each script and example invocations, see `README.md`. This file covers conventions and gotchas for editing or running scripts.

## Invocation

- Always use `uv run python scripts/<name>.py`. Never plain `python`, never `pip`. The repo's pinned environment lives in `.venv/` and is managed by `uv`.
- Scripts add `src/` to `sys.path` at import time; do not refactor them into modules under `src/drover/` without a deliberate decision. They are intentionally outside the package surface.
- The Bash sandbox blocks `127.0.0.1:11434`. Any script that reaches the local Ollama instance (`discover_taxonomy_terms.py`, `collect_classification_tuples.py`, `run_eval_experiments.py`, `organize_directory_tree.py` when configured for Ollama) needs `dangerouslyDisableSandbox: true` per `CLAUDE.md` note 13.

## When editing scripts

- Keep `README.md` in sync. New script: add a section under the appropriate group (Eval/benchmarking, Taxonomy analysis, Operational). Removed script: remove its section. Renamed script: rename the section heading.
- `check_version_consistency.py` is wired into the CI version-consistency check. If you bump `src/drover/__init__.py.__version__`, also bump `pyproject.toml [project] version` in the same commit.
- `build_eval_dashboard.py` regenerates two managed files (`eval/dashboard.html`, `eval/dashboard_data.json`). Never hand-edit either file (`CLAUDE.md` note 14). Editing the regenerator's output schema requires updating `SCHEMA_VERSION`.
- `collect_classification_tuples.py` aggregates a corpus into PII-safe counts. Filenames, document text, and per-record vendor-date-tuple joins must never appear in the output. If you add a new field, verify it is a count or aggregate, not a per-document record.
- `generate_eval_samples.py` writes to `eval/ground_truth/synthetic.jsonl`. That file is the eval ground truth; appending must preserve the form-vs-subject taxonomy rule (categories are subjects, doctypes are forms) and produce canonical pairs that satisfy `taxonomy.categories_for_domain(domain)`.

## Sandbox and gitignore touchpoints

- `eval/runs/*/*.json` is gitignored (per-doc dumps). Scripts that write into `eval/runs/<RUN_ID>/` should write `.json` for the artifact and `.stderr` for logs. The `.stderr` files are tracked.
- `eval/ground_truth/real-world.jsonl` is gitignored (PII). Never copy real-world ground-truth content into commits, comments, or capture files.

## Adding a new script

1. Use a verb-led filename: `verify_*`, `generate_*`, `benchmark_*`, `collect_*`, `build_*`, `check_*`. Follow existing naming patterns.
2. Top-of-file docstring: one-line summary, blank line, paragraph explaining when to use it, blank line, `Usage:` block with at least one `uv run python scripts/<name>.py ...` example.
3. Add a section to `README.md` matching the existing format.
4. If the script reaches Ollama, document the sandbox requirement in its docstring `Usage:` block.
