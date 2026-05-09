# Drover Smoke Suite

Re-runnable smoke suite for drover. Verifies CLI surface, the LLM
classification path, the organize move pipeline, error handling, and two
specific regressions from the May-2026 logging/converter-cache fix.

Designed for **LLM agent self-assessment** — the harness emits a stable
JSON report that downstream agents can read to answer "is drover healthy
right now, and if not, where is it broken?".

## How to run

```bash
# Full suite (requires Ollama at 127.0.0.1:11434 with gemma4:latest)
uv run python smoke/run.py

# CLI + error tests only, skip LLM-dependent ones (~10s, useful as a gate)
uv run python smoke/run.py --skip-llm

# Write report to a specific path (default: smoke/reports/<ts>.json
# plus a copy at smoke/reports/latest.json)
uv run python smoke/run.py --report-path /tmp/drover-smoke.json

# Run a single test by id
uv run python smoke/run.py --only classify.happy-path-llm
```

Exit code: 0 if every non-skipped test passed; 1 if any failed.

## Environment requirements

| Requirement | Used by | Behavior if missing |
|---|---|---|
| `uv` on PATH | all tests | suite errors out at startup |
| `drover` installed in venv (`uv sync --all-extras`) | all tests | suite errors out at startup |
| Ollama running on `127.0.0.1:11434` with `gemma4:latest` | every `*-llm` test | LLM tests marked `skipped` with `reason: ollama_unavailable` |
| Fixture PDFs in `smoke/fixtures/` | every `*-llm` test | suite errors out at startup |

## Test catalog

10 tests in 4 categories.

### cli-surface (3 tests, no LLM, <1s each)

| ID | Verifies |
|---|---|
| `cli.version` | `drover --version` exits 0, stdout matches `^drover, version \d+\.\d+\.\d+` |
| `cli.help.root` | `drover --help` exits 0, lists `classify`, `organize`, `tag`, `evaluate` subcommands |
| `cli.help.subcommands` | each of `classify --help`, `organize --help`, `tag --help`, `evaluate --help` exits 0 |

### classify (1 test, LLM, ~10-15s)

| ID | Verifies |
|---|---|
| `classify.happy-path-llm` | `drover classify <invoice.pdf>`: exit 0, stdout is JSON, `error: false`, `domain`/`category`/`doctype` non-empty, `suggested_path` matches `{domain}/{category}/{doctype}/{filename}` shape and ends in `.pdf` |

### organize (2 tests, LLM, ~15-40s combined)

| ID | Verifies |
|---|---|
| `organize.dryrun-llm` | `drover organize <fixtures/> --dest <tmp> --dry-run --report -`: exit 0, exactly 3 JSONL records on stdout, each has non-empty `suggested_path`, no files appear under dest, all 3 source PDFs still present |
| `organize.live-move-llm` | `drover organize <one-pdf> --dest <tmp> --report -`: exit 0, file exists at the reported `final_path`, original source no longer exists |

### regression (2 tests, ~15-30s combined; guard the May-2026 fix)

| ID | Verifies |
|---|---|
| `regress.logging-hygiene-llm` | `drover classify <pdf> --log-level debug`: stderr contains zero matches for any of these noise markers — `PIPELINE_PROFILING`, `connect_tcp.`, `Loading plugin`, `LayoutPredictor settings`, `HTTP Request:`, `Starting new HTTPS`, `Auto OCR model selected`, `Using selector:`, `matplotlib data path`, `detected formats:` |
| `regress.converter-cache` | Drives `DoclingLoader` directly via `uv run python -c <snippet>` and loads the **same** fixture (`bridgeport-telecom_invoice`) three times in a row, timing the full `await loader.load()` call each time (the loader's own `loader_latency_ms` only times `converter.convert()` and excludes the cold init we care about). Loading the same file three times holds content cost constant so the only thing varying between call 1 and calls 2/3 is cache state. Asserts `call_2 < 0.6 * call_1` and `call_3 < 0.6 * call_1` (cold pipeline init only fires on the first call thanks to the `_get_converter()` cache). No Ollama needed. |

### error-paths (2 tests, no LLM, <2s each)

| ID | Verifies |
|---|---|
| `error.missing-file` | `drover classify nonexistent.pdf`: exit 2, stderr mentions `does not exist` |
| `error.unsupported-ext` | `drover classify <empty>.xyz`: exit 2, stdout JSON has `error: true` and `error_code: DOCUMENT_LOAD_FAILED`, message mentions `Unsupported file type` |

## Report schema (`reports/<timestamp>.json`)

```json
{
  "schema_version": "1.0",
  "run_id": "2026-05-09T19-30-00Z",
  "started_at": "2026-05-09T19:30:00Z",
  "ended_at":   "2026-05-09T19:32:14Z",
  "duration_ms": 134812,
  "environment": {
    "drover_version": "0.1.0",
    "python_version": "3.13.x",
    "platform": "darwin",
    "ollama_available": true,
    "ollama_endpoint": "http://127.0.0.1:11434",
    "ollama_model": "gemma4:latest",
    "git_branch": "...",
    "git_sha": "..."
  },
  "summary": {
    "total": 10, "passed": 9, "failed": 1, "skipped": 0, "errored": 0,
    "by_category": {
      "cli-surface": {"total": 3, "passed": 3, "failed": 0, "skipped": 0, "errored": 0},
      "classify":    {"total": 1, "passed": 1, "failed": 0, "skipped": 0, "errored": 0},
      "organize":    {"total": 2, "passed": 2, "failed": 0, "skipped": 0, "errored": 0},
      "regression":  {"total": 2, "passed": 1, "failed": 1, "skipped": 0, "errored": 0},
      "error-paths": {"total": 2, "passed": 2, "failed": 0, "skipped": 0, "errored": 0}
    }
  },
  "regressions_for": [
    "loader-converter-caching",
    "logging-third-party-suppression"
  ],
  "tests": [
    {
      "id": "regress.logging-hygiene-llm",
      "category": "regression",
      "status": "fail",
      "duration_ms": 8421,
      "command": "uv run drover classify .../foo.pdf --log-level debug",
      "exit_code": 0,
      "skip_reason": null,
      "assertions": [
        {"id": "exit-zero", "description": "exits 0", "passed": true,  "observed": 0},
        {"id": "no-pipeline-profiling", "description": "stderr has no PIPELINE_PROFILING", "passed": false, "observed": "PIPELINE_PROFILING Stage preprocess: ..."},
        {"id": "no-httpcore-trace",     "description": "stderr has no connect_tcp.",      "passed": true,  "observed": null}
      ],
      "stdout_path": "smoke/reports/2026-05-09T19-30-00Z/regress.logging-hygiene-llm.stdout.txt",
      "stderr_path": "smoke/reports/2026-05-09T19-30-00Z/regress.logging-hygiene-llm.stderr.txt"
    }
  ]
}
```

### Schema notes for LLM agents

- **`schema_version`** — bump if the report shape changes; agents can branch on it
- **`tests[].id`** — stable slugs; safe to use as keys when diffing runs
- **`tests[].assertions[].id`** — stable per-assertion slugs so an agent can localize "which check inside `regress.logging-hygiene-llm` regressed?"
- **`tests[].assertions[].observed`** — actual observed value when an assertion fails (string, number, or null); null when the check passed and there's nothing to surface
- **`summary.by_category`** — triage rollup; lets an agent answer "is the LLM path broken or just the CLI?" with a single field lookup
- **`regressions_for`** — names of prior fixes these tests guard; if a regression test fails, the linked fix is the first place to look
- **`environment.ollama_available`** — false here means every `*-llm` test will be `skipped`; not a failure signal
- **`tests[].stdout_path` / `stderr_path`** — full captured output written to disk per test; omitted for `skipped` tests

A copy of the latest report is always written to
`smoke/reports/latest.json` for easy "give me the last result" lookup.

## Fixtures

Three synthetic PDFs from `eval/samples/synthetic/`, copied to
`smoke/fixtures/`. They were chosen for taxonomy diversity (covers
three different `domain/category/doctype` triples) so that a passing run
exercises a broader slice of the household taxonomy than any single doc
would:

| File | Expected domain | Expected category | Expected doctype |
|---|---|---|---|
| `bridgeport-telecom_invoice_2025-07-23.pdf` | utilities | internet | invoices |
| `bluefield-reference-library_manual_2025-07-28.pdf` | reference | documentation | manuals |
| `allport-insurance-group_policy_2025-10-28.pdf` | insurance | home | policies |

Note: smoke tests do **not** assert that the LLM returns these exact
labels — that's eval territory, not smoke. They only assert that
classification produces *some* well-formed taxonomy result with a valid
path shape.

## Out of scope

- **`tag` command** — requires macOS `xattr` mutation even in dry-run for
  `kMDItemUserTags`; covered by unit tests, not worth the smoke complexity
- **Non-Ollama providers** (OpenAI / Anthropic / OpenRouter) — require API
  keys, would burn money on every smoke run; covered by unit tests with
  mocked clients
- **Eval framework** (`drover evaluate`) — long-running, has its own
  reporting; smoke would duplicate without adding signal
- **Specific classification accuracy** — accuracy belongs in `eval/`, not smoke
