"""CLI integration tests for the drover organize command."""

from __future__ import annotations

import json
import sys
from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner

from drover.cli import main
from drover.models import ClassificationErrorResult, ClassificationResult, ErrorCode

if TYPE_CHECKING:
    from pathlib import Path


def _classification_for(name: str = "receipt.pdf") -> ClassificationResult:
    return ClassificationResult(
        original=name,
        suggested_path="household/finance/receipts/receipt.pdf",
        suggested_filename="receipt.pdf",
        domain="household",
        category="finance",
        doctype="receipts",
        vendor="acme",
        date="20260101",
        subject="lunch",
    )


def _patch_classify(
    monkeypatch: pytest.MonkeyPatch,
    results: dict[Path, ClassificationResult | ClassificationErrorResult],
) -> None:
    """Replace the organize classify step with a deterministic stub."""

    async def fake_classify_for_organize(
        service: Any, files: list[Path]
    ) -> dict[Path, ClassificationResult | ClassificationErrorResult]:
        return {f: results[f] for f in files if f in results}

    monkeypatch.setattr("drover.cli._classify_for_organize", fake_classify_for_organize)

    class _StubService:
        def __init__(self, *_a: Any, **_kw: Any) -> None:
            pass

    monkeypatch.setattr("drover.cli.ClassificationService", _StubService)


def test_help_lists_organize_command() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["organize", "--help"])

    assert result.exit_code == 0
    assert "Classify, optionally tag, and move" in result.output
    assert "--dest" in result.output
    assert "--copy" in result.output
    assert "--dry-run" in result.output
    assert "--report" in result.output


def test_missing_dest_exits_two(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"x")

    runner = CliRunner()
    result = runner.invoke(main, ["organize", str(src)])

    assert result.exit_code == 2


def test_invalid_tag_field_rejected_at_parse_time(tmp_path: Path) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"x")
    dest = tmp_path / "filed"

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "organize",
            str(src),
            "--dest",
            str(dest),
            "--tag-fields",
            "extension,category",
        ],
    )

    assert result.exit_code == 2
    assert "Invalid tag fields" in result.output
    # Source must not have been moved
    assert src.exists()


def test_single_file_dry_run_writes_to_stdout_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"x")
    dest = tmp_path / "filed"

    classification = _classification_for(src.name)
    _patch_classify(monkeypatch, {src.resolve(): classification})

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "organize",
            str(src),
            "--dest",
            str(dest),
            "--dry-run",
            "--report",
            "-",
        ],
    )

    assert result.exit_code == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["status"] == "would_move"
    assert record["original_path"] == str(src.resolve())
    assert record["suggested_path"] == "household/finance/receipts/receipt.pdf"
    assert record["final_destination"].endswith(
        "household/finance/receipts/receipt.pdf"
    )
    # Source untouched in dry-run
    assert src.exists()


def test_single_file_live_moves_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"hello")
    dest = tmp_path / "filed"

    classification = _classification_for(src.name)
    _patch_classify(monkeypatch, {src.resolve(): classification})

    runner = CliRunner()
    report_path = tmp_path / "report.jsonl"
    result = runner.invoke(
        main,
        [
            "organize",
            str(src),
            "--dest",
            str(dest),
            "--report",
            str(report_path),
        ],
    )

    assert result.exit_code == 0, result.stderr
    assert not src.exists()
    moved = dest / "household/finance/receipts/receipt.pdf"
    assert moved.exists()
    assert moved.read_bytes() == b"hello"

    lines = [ln for ln in report_path.read_text().splitlines() if ln.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["status"] == "moved"
    assert record["final_destination"] == str(moved.resolve())


def test_copy_mode_leaves_source_intact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"hello")
    dest = tmp_path / "filed"

    classification = _classification_for(src.name)
    _patch_classify(monkeypatch, {src.resolve(): classification})

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["organize", str(src), "--dest", str(dest), "--copy", "--report", "-"],
    )

    assert result.exit_code == 0, result.stderr
    assert src.exists()
    assert src.read_bytes() == b"hello"
    moved = dest / "household/finance/receipts/receipt.pdf"
    assert moved.exists()
    assert moved.read_bytes() == b"hello"

    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    record = json.loads(lines[0])
    assert record["status"] == "copied"


def test_skipped_exists_keeps_source_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"new")
    dest = tmp_path / "filed"
    existing = dest / "household/finance/receipts/receipt.pdf"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"old")

    classification = _classification_for(src.name)
    _patch_classify(monkeypatch, {src.resolve(): classification})

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["organize", str(src), "--dest", str(dest), "--report", "-"],
    )

    assert result.exit_code == 1
    assert src.exists()
    assert src.read_bytes() == b"new"
    assert existing.read_bytes() == b"old"

    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    assert len(lines) == 1
    record = json.loads(lines[0])
    assert record["status"] == "skipped_exists"
    assert record["final_destination"] is None


def test_unsupported_extension_is_soft_notice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unsupported extensions surface as records but do not raise the exit code."""
    bad = tmp_path / "image.unsupported"
    bad.write_bytes(b"x")
    dest = tmp_path / "filed"

    _patch_classify(monkeypatch, {})

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["organize", str(tmp_path), "--dest", str(dest), "--report", "-"],
    )

    assert result.exit_code == 0, result.stderr
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    statuses = [json.loads(ln)["status"] for ln in lines]
    assert "skipped_unsupported" in statuses


def test_directory_classify_error_records_error_and_exits_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    bad = src_dir / "bad.pdf"
    bad.write_bytes(b"x")
    dest = tmp_path / "filed"

    err = ClassificationErrorResult(
        original=bad.name,
        error_code=ErrorCode.LLM_PARSE_ERROR,
        error_message="parse failed",
    )
    _patch_classify(monkeypatch, {bad.resolve(): err})

    runner = CliRunner()
    result = runner.invoke(
        main,
        ["organize", str(src_dir), "--dest", str(dest), "--report", "-"],
    )

    assert result.exit_code == 1
    lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
    record = json.loads(lines[0])
    assert record["status"] == "error"
    assert "parse failed" in (record["error"] or "")


def test_dry_run_report_parity_with_live_run_modulo_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dry-run record set equals live-run record set up to status prefix and final_destination."""
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"hello")
    dest = tmp_path / "filed"

    classification = _classification_for(src.name)
    _patch_classify(monkeypatch, {src.resolve(): classification})

    runner = CliRunner()
    dry_report = tmp_path / "dry.jsonl"
    dry = runner.invoke(
        main,
        [
            "organize",
            str(src),
            "--dest",
            str(dest),
            "--dry-run",
            "--report",
            str(dry_report),
        ],
    )
    assert dry.exit_code == 0, dry.stderr
    dry_records = [
        json.loads(ln) for ln in dry_report.read_text().splitlines() if ln.strip()
    ]

    # Reset for the live run.
    _patch_classify(monkeypatch, {src.resolve(): classification})
    live_report = tmp_path / "live.jsonl"
    live = runner.invoke(
        main,
        [
            "organize",
            str(src),
            "--dest",
            str(dest),
            "--report",
            str(live_report),
        ],
    )
    assert live.exit_code == 0, live.stderr
    live_records = [
        json.loads(ln) for ln in live_report.read_text().splitlines() if ln.strip()
    ]

    assert len(dry_records) == len(live_records) == 1
    assert dry_records[0]["original_path"] == live_records[0]["original_path"]
    assert dry_records[0]["suggested_path"] == live_records[0]["suggested_path"]
    assert dry_records[0]["status"] == "would_move"
    assert live_records[0]["status"] == "moved"


def test_idempotent_rerun_produces_skipped_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"hello")
    dest = tmp_path / "filed"

    classification = _classification_for(src.name)
    _patch_classify(monkeypatch, {src.resolve(): classification})

    runner = CliRunner()
    first = runner.invoke(
        main, ["organize", str(src), "--dest", str(dest), "--report", "-"]
    )
    assert first.exit_code == 0, first.stderr

    # Re-run: source no longer exists so we have nothing to organize.
    # Recreate the same content and try again — this exercises the
    # collision branch.
    src.write_bytes(b"hello")
    _patch_classify(monkeypatch, {src.resolve(): classification})
    second = runner.invoke(
        main, ["organize", str(src), "--dest", str(dest), "--report", "-"]
    )
    assert second.exit_code == 1
    record = json.loads(next(ln for ln in second.stdout.splitlines() if ln.strip()))
    assert record["status"] == "skipped_exists"


@pytest.mark.skipif(
    sys.platform != "darwin", reason="--tag-fields only supported on macOS"
)
def test_tag_fields_dry_run_records_tags_applied(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"x")
    dest = tmp_path / "filed"

    classification = _classification_for(src.name)
    _patch_classify(monkeypatch, {src.resolve(): classification})

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "organize",
            str(src),
            "--dest",
            str(dest),
            "--dry-run",
            "--tag-fields",
            "category,doctype",
            "--report",
            "-",
        ],
    )

    assert result.exit_code == 0, result.stderr
    record = json.loads(next(ln for ln in result.stdout.splitlines() if ln.strip()))
    fields = {entry["field"]: entry["value"] for entry in record["tags_applied"]}
    assert fields == {"category": "finance", "doctype": "receipts"}


@pytest.mark.skipif(
    sys.platform != "darwin", reason="--tag-fields only supported on macOS"
)
def test_tag_failure_after_successful_move_does_not_roll_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Tag-step failure must leave the move intact and emit a moved record.

    The tags_applied list is empty because tagging never succeeded; the
    status is ``moved`` because the move did succeed.
    """
    src = tmp_path / "doc.pdf"
    src.write_bytes(b"hello")
    dest = tmp_path / "filed"

    classification = _classification_for(src.name)
    _patch_classify(monkeypatch, {src.resolve(): classification})

    from drover.actions.tag import TagAction

    def raise_on_plan(self: TagAction, file: Path, result: Any) -> None:
        raise RuntimeError("simulated tag failure")

    monkeypatch.setattr(TagAction, "plan", raise_on_plan)

    runner = CliRunner()
    result = runner.invoke(
        main,
        [
            "organize",
            str(src),
            "--dest",
            str(dest),
            "--tag-fields",
            "category,doctype",
            "--report",
            "-",
        ],
    )

    assert result.exit_code == 0, result.stderr
    moved = dest / "household/finance/receipts/receipt.pdf"
    assert moved.exists()
    assert moved.read_bytes() == b"hello"
    assert not src.exists()

    record = json.loads(next(ln for ln in result.stdout.splitlines() if ln.strip()))
    assert record["status"] == "moved"
    assert record["tags_applied"] == []
    assert record["error"] is None
