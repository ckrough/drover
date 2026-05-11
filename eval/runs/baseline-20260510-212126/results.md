# Baseline — synthetic eval (post python-semantic-release migration)

| Field | Value |
|---|---|
| Date | 2026-05-10 |
| Commit | f804c3c (clean source tree; `-dirty` suffix observed in raw run JSON came from a touch of `.claude/scheduled_tasks.lock` during a wakeup poll and was scrubbed) |
| Branch | worktree-golden-churning-lagoon |
| Corpus | synthetic (80 docs) |
| Provider / model | ollama / gemma4:latest |
| Loader | docling |
| OCR backend | ocrmac (Apple Vision via the `ocr-mac` extra) |
| Wallclock | 1432 s (~23.9 minutes, sequential, concurrency=1) |

## Accuracy

| Metric | Result |
|---|---|
| Domain | 86.2% |
| Category | 61.2% |
| Doctype | 91.2% |
| Vendor | 91.2% |
| Date | 90.0% |
| **Entity** | **70.0%** (14 / 20 labelled docs) |
| Errors | 0 |

## Purpose

Re-establishes the canonical accuracy baseline at the current `main` tip (commit `f804c3c`, `feat: adopt python-semantic-release with single-source version (#35)`). All subsequent runs are charted against this point in `eval/charts/accuracy-over-time.png` and `eval/dashboard.html`.

## Deltas vs prior baseline (2026-04-29)

| Metric | 2026-04-29 | This run | Delta |
|---|---|---|---|
| Domain | 87.5% | 86.2% | -1.3 pp |
| Category | 40.0% | 61.2% | +21.2 pp |
| Doctype | 86.2% | 91.2% | +5.0 pp |
| Vendor | 78.8% | 91.2% | +12.4 pp |
| Date | 88.8% | 90.0% | +1.2 pp |

Category, vendor, and doctype show the largest gains: the Round 4 taxonomy refactor (plural doctypes, LCGFT/schema.org alignment), Docling full-page OCR with the ocrmac backend, the correspondence/reference/hierarchy demotions, the lifestyle/entertainment category additions, and dropping the `personal` domain all land between the two baselines.
