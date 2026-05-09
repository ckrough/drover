#!/usr/bin/env python3
"""Drover smoke-test harness.

Spec: smoke/README.md
Re-runnable smoke suite. Emits a stable JSON report for LLM-agent self-assessment.

Usage:
  uv run python smoke/run.py
  uv run python smoke/run.py --skip-llm
  uv run python smoke/run.py --only classify.happy-path-llm
  uv run python smoke/run.py --report-path /tmp/drover-smoke.json
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

SCHEMA_VERSION = "1.0"
REGRESSIONS_FOR = ["loader-converter-caching", "logging-third-party-suppression"]

REPO_ROOT = Path(__file__).resolve().parent.parent
SMOKE_ROOT = Path(__file__).resolve().parent
FIXTURES_DIR = SMOKE_ROOT / "fixtures"
REPORTS_DIR = SMOKE_ROOT / "reports"

FIXTURE_INVOICE = FIXTURES_DIR / "bridgeport-telecom_invoice_2025-07-23.pdf"
FIXTURE_MANUAL = FIXTURES_DIR / "bluefield-reference-library_manual_2025-07-28.pdf"
FIXTURE_POLICY = FIXTURES_DIR / "allport-insurance-group_policy_2025-10-28.pdf"
ALL_FIXTURES = [FIXTURE_INVOICE, FIXTURE_MANUAL, FIXTURE_POLICY]

OLLAMA_HOST = "127.0.0.1"
OLLAMA_PORT = 11434
OLLAMA_MODEL = "gemma4:latest"

LOGGING_NOISE_MARKERS = [
    "PIPELINE_PROFILING",
    "connect_tcp.",
    "Loading plugin",
    "LayoutPredictor settings",
    "HTTP Request:",
    "Starting new HTTPS",
    "Auto OCR model selected",
    "Using selector:",
    "matplotlib data path",
    "detected formats:",
]

CACHE_LATENCY_RATIO = 0.6  # files 2/3 must be < 60% of file 1


@dataclass
class Assertion:
    id: str
    description: str
    passed: bool
    observed: Any = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "description": self.description,
            "passed": self.passed,
            "observed": self.observed,
        }


@dataclass
class TestResult:
    id: str
    category: str
    status: str  # pass | fail | skip | error
    duration_ms: int
    command: str | None = None
    exit_code: int | None = None
    skip_reason: str | None = None
    assertions: list[Assertion] = field(default_factory=list)
    stdout_path: str | None = None
    stderr_path: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "category": self.category,
            "status": self.status,
            "duration_ms": self.duration_ms,
            "command": self.command,
            "exit_code": self.exit_code,
            "skip_reason": self.skip_reason,
            "assertions": [a.to_dict() for a in self.assertions],
            "stdout_path": self.stdout_path,
            "stderr_path": self.stderr_path,
            "error_message": self.error_message,
        }


@dataclass
class TestSpec:
    id: str
    category: str
    requires_llm: bool
    runner: Callable[["TestContext"], TestResult]


@dataclass
class TestContext:
    run_dir: Path  # per-run capture dir for stdout/stderr files
    ollama_available: bool


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def slug_ts(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H-%M-%SZ")


def run_drover(
    args: list[str],
    ctx: TestContext,
    test_id: str,
    timeout: int = 180,
) -> tuple[int, str, str, int, str]:
    """Run `uv run drover ...`. Returns (exit, stdout, stderr, duration_ms, cmd_str)."""
    cmd = ["uv", "run", "drover", *args]
    cmd_str = " ".join(cmd)
    env = os.environ.copy()
    if "UV_CACHE_DIR" not in env:
        tmp = os.environ.get("TMPDIR", "/tmp")
        env["UV_CACHE_DIR"] = str(Path(tmp) / "uv-cache")
    start = time.monotonic()
    proc = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    duration_ms = int((time.monotonic() - start) * 1000)

    stdout_path = ctx.run_dir / f"{test_id}.stdout.txt"
    stderr_path = ctx.run_dir / f"{test_id}.stderr.txt"
    stdout_path.write_text(proc.stdout, encoding="utf-8")
    stderr_path.write_text(proc.stderr, encoding="utf-8")

    return proc.returncode, proc.stdout, proc.stderr, duration_ms, cmd_str


def make_skipped(spec: TestSpec, reason: str) -> TestResult:
    return TestResult(
        id=spec.id,
        category=spec.category,
        status="skip",
        duration_ms=0,
        skip_reason=reason,
    )


def make_error(spec: TestSpec, err: str, duration_ms: int) -> TestResult:
    return TestResult(
        id=spec.id,
        category=spec.category,
        status="error",
        duration_ms=duration_ms,
        error_message=err,
    )


def finalize(spec: TestSpec, result: TestResult) -> TestResult:
    if any(not a.passed for a in result.assertions):
        result.status = "fail"
    else:
        result.status = "pass"
    result.id = spec.id
    result.category = spec.category
    return result


# -------- individual tests --------


def t_cli_version(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["cli.version"]
    exit_code, stdout, _, dur, cmd = run_drover(["--version"], ctx, spec.id)
    semver_ok = bool(re.search(r"^drover, version \d+\.\d+\.\d+", stdout.strip()))
    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=dur,
            command=cmd,
            exit_code=exit_code,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=[
                Assertion("exit-zero", "exits 0", exit_code == 0, exit_code),
                Assertion(
                    "version-format",
                    "stdout matches 'drover, version <semver>'",
                    semver_ok,
                    stdout.strip().splitlines()[0] if stdout.strip() else None,
                ),
            ],
        ),
    )


def t_cli_help_root(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["cli.help.root"]
    exit_code, stdout, _, dur, cmd = run_drover(["--help"], ctx, spec.id)
    expected = ["classify", "organize", "tag", "evaluate"]
    missing = [s for s in expected if s not in stdout]
    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=dur,
            command=cmd,
            exit_code=exit_code,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=[
                Assertion("exit-zero", "exits 0", exit_code == 0, exit_code),
                Assertion(
                    "lists-subcommands",
                    "lists classify/organize/tag/evaluate",
                    not missing,
                    f"missing: {missing}" if missing else None,
                ),
            ],
        ),
    )


def t_cli_help_subcommands(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["cli.help.subcommands"]
    subs = ["classify", "organize", "tag", "evaluate"]
    assertions: list[Assertion] = []
    total_dur = 0
    last_cmd = ""
    for sub in subs:
        exit_code, _, _, dur, cmd = run_drover(
            [sub, "--help"], ctx, f"{spec.id}.{sub}"
        )
        total_dur += dur
        last_cmd = cmd
        assertions.append(
            Assertion(
                f"{sub}-exit-zero",
                f"`drover {sub} --help` exits 0",
                exit_code == 0,
                exit_code,
            )
        )
    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=total_dur,
            command=last_cmd,
            assertions=assertions,
        ),
    )


def t_classify_happy_path(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["classify.happy-path-llm"]
    exit_code, stdout, _, dur, cmd = run_drover(
        ["classify", str(FIXTURE_INVOICE)], ctx, spec.id
    )
    parsed: dict[str, Any] | None = None
    parse_err: str | None = None
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError as e:
        parse_err = str(e)

    assertions: list[Assertion] = [
        Assertion("exit-zero", "exits 0", exit_code == 0, exit_code),
        Assertion(
            "stdout-is-json",
            "stdout parses as JSON",
            parsed is not None,
            parse_err,
        ),
    ]
    if parsed is not None:
        domain = parsed.get("domain")
        category = parsed.get("category")
        doctype = parsed.get("doctype")
        suggested_path = parsed.get("suggested_path", "")
        assertions.extend(
            [
                Assertion(
                    "error-flag-false",
                    "error field is false",
                    parsed.get("error") is False,
                    parsed.get("error"),
                ),
                Assertion(
                    "domain-non-empty",
                    "domain is non-empty",
                    bool(domain),
                    domain,
                ),
                Assertion(
                    "category-non-empty",
                    "category is non-empty",
                    bool(category),
                    category,
                ),
                Assertion(
                    "doctype-non-empty",
                    "doctype is non-empty",
                    bool(doctype),
                    doctype,
                ),
                Assertion(
                    "path-shape-matches",
                    "suggested_path matches {domain}/{category}/{doctype}/<file>.pdf",
                    bool(domain)
                    and bool(category)
                    and bool(doctype)
                    and suggested_path.startswith(f"{domain}/{category}/{doctype}/")
                    and suggested_path.endswith(".pdf"),
                    suggested_path,
                ),
            ]
        )

    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=dur,
            command=cmd,
            exit_code=exit_code,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=assertions,
        ),
    )


def _parse_jsonl_records(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return out


def t_organize_dryrun(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["organize.dryrun-llm"]
    with tempfile.TemporaryDirectory(prefix="drover-smoke-dest-") as dest:
        dest_path = Path(dest)
        exit_code, stdout, _, dur, cmd = run_drover(
            [
                "organize",
                str(FIXTURES_DIR),
                "--dest",
                str(dest_path),
                "--dry-run",
                "--report",
                "-",
            ],
            ctx,
            spec.id,
            timeout=300,
        )
        records = _parse_jsonl_records(stdout)
        record_count = len(records)
        all_have_path = all(r.get("suggested_path") for r in records)
        nothing_in_dest = not any(dest_path.rglob("*.pdf"))
        sources_intact = all(p.exists() for p in ALL_FIXTURES)

    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=dur,
            command=cmd,
            exit_code=exit_code,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=[
                Assertion("exit-zero", "exits 0", exit_code == 0, exit_code),
                Assertion(
                    "three-records",
                    "stdout JSONL has exactly 3 records",
                    record_count == 3,
                    record_count,
                ),
                Assertion(
                    "all-have-suggested-path",
                    "every record has non-empty suggested_path",
                    all_have_path,
                    None if all_have_path else [r.get("suggested_path") for r in records],
                ),
                Assertion(
                    "dest-untouched",
                    "no PDFs created under --dest (dry-run)",
                    nothing_in_dest,
                    None if nothing_in_dest else "dest contains pdfs",
                ),
                Assertion(
                    "sources-intact",
                    "all source fixture files still exist",
                    sources_intact,
                    None if sources_intact else "one or more sources missing",
                ),
            ],
        ),
    )


def t_organize_live_move(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["organize.live-move-llm"]
    with (
        tempfile.TemporaryDirectory(prefix="drover-smoke-src-") as src_dir,
        tempfile.TemporaryDirectory(prefix="drover-smoke-dest-") as dest_dir,
    ):
        src_path = Path(src_dir)
        dest_path = Path(dest_dir)
        # Use a copy of the manual fixture so the live move doesn't disturb the canonical fixture.
        live_src = src_path / FIXTURE_MANUAL.name
        shutil.copy2(FIXTURE_MANUAL, live_src)

        exit_code, stdout, _, dur, cmd = run_drover(
            [
                "organize",
                str(live_src),
                "--dest",
                str(dest_path),
                "--report",
                "-",
            ],
            ctx,
            spec.id,
            timeout=300,
        )
        records = _parse_jsonl_records(stdout)
        final_path: str | None = None
        for r in records:
            for action in r.get("actions", []) or []:
                fp = action.get("final_path")
                if fp:
                    final_path = fp
        # Fall back to suggested_path joined with dest if no action final_path was reported.
        if final_path is None and records:
            sp = records[0].get("suggested_path")
            if sp:
                final_path = str(dest_path / sp)
        moved_exists = bool(final_path) and Path(final_path).exists()
        source_gone = not live_src.exists()

    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=dur,
            command=cmd,
            exit_code=exit_code,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=[
                Assertion("exit-zero", "exits 0", exit_code == 0, exit_code),
                Assertion(
                    "moved-file-exists",
                    "file exists at reported final_path under dest",
                    moved_exists,
                    final_path,
                ),
                Assertion(
                    "source-removed",
                    "source PDF no longer exists",
                    source_gone,
                    str(live_src),
                ),
            ],
        ),
    )


def t_regress_logging_hygiene(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["regress.logging-hygiene-llm"]
    exit_code, _, stderr, dur, cmd = run_drover(
        ["classify", str(FIXTURE_INVOICE), "--log-level", "debug"],
        ctx,
        spec.id,
    )
    assertions: list[Assertion] = [
        Assertion("exit-zero", "exits 0", exit_code == 0, exit_code),
    ]
    for marker in LOGGING_NOISE_MARKERS:
        # Build a slug from the marker for the assertion id.
        marker_slug = re.sub(r"[^a-z0-9]+", "-", marker.lower()).strip("-")
        present = marker in stderr
        observed: str | None = None
        if present:
            for line in stderr.splitlines():
                if marker in line:
                    observed = line[:200]
                    break
        assertions.append(
            Assertion(
                f"no-{marker_slug}",
                f"stderr has no '{marker}'",
                not present,
                observed,
            )
        )
    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=dur,
            command=cmd,
            exit_code=exit_code,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=assertions,
        ),
    )


_CACHE_PROBE_SNIPPET = """
import asyncio, json, sys, time
from pathlib import Path
from drover.loader import DoclingLoader

async def main(path, repeats):
    loader = DoclingLoader()
    out = []
    for _ in range(repeats):
        start = time.perf_counter()
        await loader.load(Path(path))
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        out.append({"path": path, "load_total_ms": elapsed_ms})
    print(json.dumps(out))

asyncio.run(main(sys.argv[1], int(sys.argv[2])))
"""


def t_regress_converter_cache(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["regress.converter-cache"]
    # Drive DoclingLoader directly so we measure the exact code path the cache
    # fix lives on, without depending on `loader_latency_ms` being plumbed
    # through the organize JSONL report.
    # Load the SAME fixture 3 times: content cost is held constant, so any
    # latency drop between call 1 and calls 2/3 is attributable to the
    # converter cache (cold init only fires on the first call).
    cmd_args = [
        "uv",
        "run",
        "python",
        "-c",
        _CACHE_PROBE_SNIPPET,
        str(FIXTURE_INVOICE),
        "3",
    ]
    env = os.environ.copy()
    if "UV_CACHE_DIR" not in env:
        tmp = os.environ.get("TMPDIR", "/tmp")
        env["UV_CACHE_DIR"] = str(Path(tmp) / "uv-cache")
    start = time.monotonic()
    proc = subprocess.run(
        cmd_args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=300,
        env=env,
        check=False,
    )
    duration_ms = int((time.monotonic() - start) * 1000)
    (ctx.run_dir / f"{spec.id}.stdout.txt").write_text(proc.stdout, encoding="utf-8")
    (ctx.run_dir / f"{spec.id}.stderr.txt").write_text(proc.stderr, encoding="utf-8")

    records: list[dict[str, Any]] = []
    parse_err: str | None = None
    stripped = proc.stdout.strip()
    if not stripped:
        parse_err = "empty stdout"
    else:
        try:
            records = json.loads(stripped.splitlines()[-1])
        except json.JSONDecodeError as e:
            parse_err = str(e)

    latencies = [r.get("load_total_ms") for r in records]
    have_three = len(latencies) == 3 and all(
        isinstance(x, int | float) for x in latencies
    )

    assertions: list[Assertion] = [
        Assertion("exit-zero", "exits 0", proc.returncode == 0, proc.returncode),
        Assertion(
            "stdout-is-json",
            "probe stdout parses as JSON",
            parse_err is None,
            parse_err,
        ),
        Assertion(
            "three-load-totals",
            "probe returned 3 numeric load_total_ms values",
            have_three,
            latencies,
        ),
    ]
    if have_three:
        first, second, third = latencies
        threshold = first * CACHE_LATENCY_RATIO
        ratio_2 = second / first if first else None
        ratio_3 = third / first if first else None
        assertions.extend(
            [
                Assertion(
                    "file2-faster-than-threshold",
                    f"file 2 load_total_ms < {CACHE_LATENCY_RATIO * 100:.0f}% of file 1",
                    second < threshold,
                    {"file_1_ms": first, "file_2_ms": second, "ratio": ratio_2},
                ),
                Assertion(
                    "file3-faster-than-threshold",
                    f"file 3 load_total_ms < {CACHE_LATENCY_RATIO * 100:.0f}% of file 1",
                    third < threshold,
                    {"file_1_ms": first, "file_3_ms": third, "ratio": ratio_3},
                ),
            ]
        )
    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=duration_ms,
            command=" ".join(cmd_args[:5]) + " ... <fixtures>",
            exit_code=proc.returncode,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=assertions,
        ),
    )


def t_error_missing_file(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["error.missing-file"]
    exit_code, _, stderr, dur, cmd = run_drover(
        ["classify", "nonexistent-smoke-file.pdf"], ctx, spec.id
    )
    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=dur,
            command=cmd,
            exit_code=exit_code,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=[
                Assertion(
                    "exit-2",
                    "exits 2 (Click usage error)",
                    exit_code == 2,
                    exit_code,
                ),
                Assertion(
                    "stderr-mentions-missing",
                    "stderr mentions 'does not exist'",
                    "does not exist" in stderr,
                    None if "does not exist" in stderr else stderr[:200],
                ),
            ],
        ),
    )


def t_error_unsupported_ext(ctx: TestContext) -> TestResult:
    spec = SPECS_BY_ID["error.unsupported-ext"]
    with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
        bogus = Path(f.name)
    try:
        exit_code, stdout, _, dur, cmd = run_drover(
            ["classify", str(bogus)], ctx, spec.id
        )
        parsed: dict[str, Any] | None = None
        parse_err: str | None = None
        try:
            parsed = json.loads(stdout)
        except json.JSONDecodeError as e:
            parse_err = str(e)

        assertions: list[Assertion] = [
            Assertion("exit-2", "exits 2 (drover CLI error code)", exit_code == 2, exit_code),
            Assertion(
                "stdout-is-json",
                "stdout parses as JSON",
                parsed is not None,
                parse_err,
            ),
        ]
        if parsed is not None:
            assertions.extend(
                [
                    Assertion(
                        "error-flag-true",
                        "error field is true",
                        parsed.get("error") is True,
                        parsed.get("error"),
                    ),
                    Assertion(
                        "error-code-doc-load-failed",
                        "error_code is DOCUMENT_LOAD_FAILED",
                        parsed.get("error_code") == "DOCUMENT_LOAD_FAILED",
                        parsed.get("error_code"),
                    ),
                    Assertion(
                        "message-mentions-unsupported",
                        "error_message mentions 'Unsupported file type'",
                        "Unsupported file type" in (parsed.get("error_message") or ""),
                        parsed.get("error_message"),
                    ),
                ]
            )
    finally:
        bogus.unlink(missing_ok=True)

    return finalize(
        spec,
        TestResult(
            id=spec.id,
            category=spec.category,
            status="pass",
            duration_ms=dur,
            command=cmd,
            exit_code=exit_code,
            stdout_path=str(ctx.run_dir / f"{spec.id}.stdout.txt"),
            stderr_path=str(ctx.run_dir / f"{spec.id}.stderr.txt"),
            assertions=assertions,
        ),
    )


# -------- registry --------

SPECS: list[TestSpec] = [
    TestSpec("cli.version", "cli-surface", False, t_cli_version),
    TestSpec("cli.help.root", "cli-surface", False, t_cli_help_root),
    TestSpec("cli.help.subcommands", "cli-surface", False, t_cli_help_subcommands),
    TestSpec("classify.happy-path-llm", "classify", True, t_classify_happy_path),
    TestSpec("organize.dryrun-llm", "organize", True, t_organize_dryrun),
    TestSpec("organize.live-move-llm", "organize", True, t_organize_live_move),
    TestSpec(
        "regress.logging-hygiene-llm",
        "regression",
        True,
        t_regress_logging_hygiene,
    ),
    TestSpec(
        "regress.converter-cache",
        "regression",
        False,
        t_regress_converter_cache,
    ),
    TestSpec("error.missing-file", "error-paths", False, t_error_missing_file),
    TestSpec("error.unsupported-ext", "error-paths", False, t_error_unsupported_ext),
]
SPECS_BY_ID = {s.id: s for s in SPECS}


# -------- environment probes --------


def ollama_available(host: str = OLLAMA_HOST, port: int = OLLAMA_PORT) -> bool:
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


def detect_drover_version() -> str:
    try:
        out = subprocess.run(
            ["uv", "run", "drover", "--version"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        line = out.stdout.strip().splitlines()[0] if out.stdout.strip() else ""
        m = re.search(r"version (\S+)", line)
        return m.group(1) if m else "unknown"
    except (subprocess.SubprocessError, OSError):
        return "unknown"


def git_info() -> tuple[str, str]:
    def _git(args: list[str]) -> str:
        try:
            out = subprocess.run(
                ["git", *args],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
            return out.stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return ""

    return _git(["rev-parse", "--abbrev-ref", "HEAD"]), _git(["rev-parse", "HEAD"])


def fixtures_present() -> tuple[bool, list[Path]]:
    missing = [p for p in ALL_FIXTURES if not p.exists()]
    return (not missing), missing


# -------- main --------


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Drover smoke-test harness")
    p.add_argument(
        "--skip-llm",
        action="store_true",
        help="Skip every test that requires Ollama.",
    )
    p.add_argument(
        "--only",
        action="append",
        default=[],
        help="Run only the named test id (repeatable).",
    )
    p.add_argument(
        "--report-path",
        default=None,
        help=(
            "Write report to this path. Default: "
            "smoke/reports/<timestamp>.json plus reports/latest.json"
        ),
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-test progress lines on stderr.",
    )
    return p.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    fixtures_ok, missing = fixtures_present()
    if not fixtures_ok:
        print(
            f"ERROR: missing fixture PDFs: {[str(p) for p in missing]}",
            file=sys.stderr,
        )
        return 2

    started = now_utc()
    run_id = slug_ts(started)
    run_dir = REPORTS_DIR / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    ollama_up = ollama_available()
    ctx = TestContext(run_dir=run_dir, ollama_available=ollama_up)

    selected: list[TestSpec] = SPECS
    if args.only:
        unknown = [s for s in args.only if s not in SPECS_BY_ID]
        if unknown:
            print(f"ERROR: unknown test ids: {unknown}", file=sys.stderr)
            return 2
        selected = [SPECS_BY_ID[s] for s in args.only]

    results: list[TestResult] = []
    for spec in selected:
        if not args.quiet:
            print(f"-> {spec.id} ...", file=sys.stderr, flush=True)
        if spec.requires_llm and (args.skip_llm or not ollama_up):
            reason = "skipped_via_flag" if args.skip_llm else "ollama_unavailable"
            results.append(make_skipped(spec, reason))
            if not args.quiet:
                print(f"   SKIP ({reason})", file=sys.stderr)
            continue
        t0 = time.monotonic()
        try:
            res = spec.runner(ctx)
        except Exception as e:  # noqa: BLE001 — capture test-runner errors; KeyboardInterrupt/SystemExit still propagate
            dur_ms = int((time.monotonic() - t0) * 1000)
            res = make_error(spec, f"{type(e).__name__}: {e}", dur_ms)
        results.append(res)
        if not args.quiet:
            print(f"   {res.status.upper()} ({res.duration_ms} ms)", file=sys.stderr)

    ended = now_utc()
    duration_ms = int((ended - started).total_seconds() * 1000)

    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        bucket = by_category.setdefault(
            r.category, {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "errored": 0}
        )
        bucket["total"] += 1
        if r.status == "pass":
            bucket["passed"] += 1
        elif r.status == "fail":
            bucket["failed"] += 1
        elif r.status == "skip":
            bucket["skipped"] += 1
        elif r.status == "error":
            bucket["errored"] += 1

    branch, sha = git_info()
    report = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "started_at": iso(started),
        "ended_at": iso(ended),
        "duration_ms": duration_ms,
        "environment": {
            "drover_version": detect_drover_version(),
            "python_version": platform.python_version(),
            "platform": sys.platform,
            "ollama_available": ollama_up,
            "ollama_endpoint": f"http://{OLLAMA_HOST}:{OLLAMA_PORT}",
            "ollama_model": OLLAMA_MODEL,
            "git_branch": branch,
            "git_sha": sha,
        },
        "summary": {
            "total": len(results),
            "passed": sum(1 for r in results if r.status == "pass"),
            "failed": sum(1 for r in results if r.status == "fail"),
            "skipped": sum(1 for r in results if r.status == "skip"),
            "errored": sum(1 for r in results if r.status == "error"),
            "by_category": by_category,
        },
        "regressions_for": REGRESSIONS_FOR,
        "tests": [r.to_dict() for r in results],
    }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    default_report_path = REPORTS_DIR / f"{run_id}.json"
    if args.report_path:
        report_path = Path(args.report_path)
        report_path.parent.mkdir(parents=True, exist_ok=True)
    else:
        report_path = default_report_path
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    latest_path = REPORTS_DIR / "latest.json"
    latest_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if not args.quiet:
        s = report["summary"]
        print(
            f"\nDone in {duration_ms} ms — "
            f"passed={s['passed']} failed={s['failed']} "
            f"skipped={s['skipped']} errored={s['errored']}",
            file=sys.stderr,
        )
        print(f"Report: {report_path}", file=sys.stderr)
        print(f"Latest: {latest_path}", file=sys.stderr)

    failed_or_errored = report["summary"]["failed"] + report["summary"]["errored"]
    return 0 if failed_or_errored == 0 else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
