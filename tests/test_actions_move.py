"""Unit tests for MoveAction."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from drover.actions.move import MoveAction, MoveStatus
from drover.models import ClassificationResult


def _classification(
    suggested_path: str = "household/finance/receipts/receipt.pdf",
) -> ClassificationResult:
    return ClassificationResult(
        original="receipt.pdf",
        suggested_path=suggested_path,
        suggested_filename=Path(suggested_path).name,
        domain="household",
        category="finance",
        doctype="receipts",
        vendor="acme",
        date="20260101",
        subject="lunch",
    )


def test_plan_would_move_when_destination_missing(tmp_path: Path) -> None:
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"data")

    action = MoveAction(dest_root=tmp_path / "filed")
    plan = action.plan(source, _classification())

    assert plan.changes["status"] == MoveStatus.WOULD_MOVE.value
    assert plan.changes["halt_chain"] is False
    expected = (tmp_path / "filed" / "household/finance/receipts/receipt.pdf").resolve()
    assert Path(plan.changes["destination"]) == expected
    assert plan.changes["final_path"] == expected


def test_plan_would_skip_exists_when_destination_present(tmp_path: Path) -> None:
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"data")

    dest_root = tmp_path / "filed"
    existing = dest_root / "household/finance/receipts/receipt.pdf"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"existing")

    action = MoveAction(dest_root=dest_root)
    plan = action.plan(source, _classification())

    assert plan.changes["status"] == MoveStatus.WOULD_SKIP_EXISTS.value
    assert plan.changes["halt_chain"] is True
    assert plan.changes["final_path"] == source


def test_execute_move_same_volume(tmp_path: Path) -> None:
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"hello")

    action = MoveAction(dest_root=tmp_path / "filed")
    plan = action.plan(source, _classification())
    result = action.execute(plan)

    assert result.success is True
    assert result.changes["status"] == MoveStatus.MOVED.value
    dest = Path(result.changes["destination"])
    assert dest.exists()
    assert dest.read_bytes() == b"hello"
    assert not source.exists()


def test_execute_copy_leaves_source_intact(tmp_path: Path) -> None:
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"hello")

    action = MoveAction(dest_root=tmp_path / "filed", copy=True)
    plan = action.plan(source, _classification())
    result = action.execute(plan)

    assert result.success is True
    assert result.changes["status"] == MoveStatus.COPIED.value
    assert source.exists()
    assert source.read_bytes() == b"hello"
    dest = Path(result.changes["destination"])
    assert dest.exists()
    assert dest.read_bytes() == b"hello"


def test_execute_skip_when_destination_exists(tmp_path: Path) -> None:
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"new")

    dest_root = tmp_path / "filed"
    existing = dest_root / "household/finance/receipts/receipt.pdf"
    existing.parent.mkdir(parents=True)
    existing.write_bytes(b"old")

    action = MoveAction(dest_root=dest_root)
    plan = action.plan(source, _classification())
    result = action.execute(plan)

    assert result.success is True
    assert result.changes["status"] == MoveStatus.SKIPPED_EXISTS.value
    assert result.changes["halt_chain"] is True
    assert source.exists()
    assert source.read_bytes() == b"new"
    assert existing.read_bytes() == b"old"


def test_execute_creates_intermediate_directories(tmp_path: Path) -> None:
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"hello")

    dest_root = tmp_path / "filed-deep"
    action = MoveAction(dest_root=dest_root)
    plan = action.plan(
        source,
        _classification("alpha/beta/gamma/receipt.pdf"),
    )
    result = action.execute(plan)

    assert result.success is True
    dest = Path(result.changes["destination"])
    assert dest.exists()
    assert dest.parent == dest_root / "alpha" / "beta" / "gamma"


def test_execute_cross_volume_copy_then_remove(tmp_path: Path) -> None:
    """When Path.rename raises (cross-volume), we fall back to copy + unlink."""
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"hello")

    action = MoveAction(dest_root=tmp_path / "filed")
    plan = action.plan(source, _classification())

    def raising_rename(self: Path, target: Path) -> None:
        raise OSError("simulated cross-volume")

    with patch.object(Path, "rename", raising_rename):
        result = action.execute(plan)

    assert result.success is True
    assert result.changes["status"] == MoveStatus.MOVED.value
    dest = Path(result.changes["destination"])
    assert dest.exists()
    assert dest.read_bytes() == b"hello"
    assert not source.exists()


def test_execute_cross_volume_partial_failure_reports_error(tmp_path: Path) -> None:
    """Copy succeeds, source removal fails → error result with partial=True."""
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"hello")

    action = MoveAction(dest_root=tmp_path / "filed")
    plan = action.plan(source, _classification())

    def raising_rename(self: Path, target: Path) -> None:
        raise OSError("cross-volume")

    def raising_unlink(self: Path) -> None:
        raise OSError("simulated unlink failure")

    with (
        patch.object(Path, "rename", raising_rename),
        patch.object(Path, "unlink", raising_unlink),
    ):
        result = action.execute(plan)

    assert result.success is False
    assert result.changes["status"] == MoveStatus.ERROR.value
    assert result.changes.get("partial") is True
    assert source.exists()  # source not removed
    dest = Path(result.changes["destination"])
    assert dest.exists()  # destination has the copy


def test_execute_error_leaves_source_intact(tmp_path: Path) -> None:
    """If the destination write raises, the source must be untouched."""
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"hello")

    action = MoveAction(dest_root=tmp_path / "filed")
    plan = action.plan(source, _classification())

    def raising_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        raise OSError("denied")

    with patch.object(Path, "mkdir", raising_mkdir):
        result = action.execute(plan)

    assert result.success is False
    assert result.changes["status"] == MoveStatus.ERROR.value
    assert source.exists()
    assert source.read_bytes() == b"hello"


def test_dry_run_idempotent(tmp_path: Path) -> None:
    """Calling plan twice in a row yields identical changes (no FS mutation)."""
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"hello")

    action = MoveAction(dest_root=tmp_path / "filed")
    plan1 = action.plan(source, _classification())
    plan2 = action.plan(source, _classification())

    assert plan1.changes == plan2.changes
    assert source.exists()
    assert not Path(plan1.changes["destination"]).exists()


@pytest.mark.skipif(sys.platform == "win32", reason="symlink semantics differ")
def test_plan_treats_broken_symlink_at_destination_as_collision(tmp_path: Path) -> None:
    """A broken symlink at the destination must be reported as skipped_exists.

    Without this guard, ``Path.exists()`` returns False for a broken
    symlink and the planner would proceed to a copy/move that follows
    the symlink to whatever it points at.
    """
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"new")

    dest_root = tmp_path / "filed"
    dest_path = dest_root / "household/finance/receipts/receipt.pdf"
    dest_path.parent.mkdir(parents=True)
    nonexistent_target = tmp_path / "outside" / "victim.txt"
    dest_path.symlink_to(nonexistent_target)

    assert not dest_path.exists()  # broken symlink — exists() is False
    assert dest_path.is_symlink()  # but is_symlink() is True

    action = MoveAction(dest_root=dest_root, copy=True)
    plan = action.plan(source, _classification())

    assert plan.changes["status"] == MoveStatus.WOULD_SKIP_EXISTS.value
    assert plan.changes["halt_chain"] is True


@pytest.mark.skipif(sys.platform == "win32", reason="symlink semantics differ")
def test_execute_refuses_symlink_appearing_after_plan(tmp_path: Path) -> None:
    """Symlinks planted between plan and execute must trigger an error, not a write-through.

    Even if ``MoveAction.plan`` saw a clear destination, an attacker (or
    just another process) could plant a symlink before execute. The
    execute path must refuse the write rather than letting shutil.copy2
    follow it.
    """
    source = tmp_path / "incoming" / "receipt.pdf"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"hello")

    action = MoveAction(dest_root=tmp_path / "filed", copy=True)
    plan = action.plan(source, _classification())
    # Plan saw clear destination; now plant a broken symlink.
    dest_path = Path(plan.changes["destination"])
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    victim = tmp_path / "victim.txt"
    dest_path.symlink_to(victim)

    result = action.execute(plan)

    assert result.success is False
    assert result.changes["status"] == MoveStatus.ERROR.value
    assert source.exists()
    assert source.read_bytes() == b"hello"
    # Crucially, the symlink target was not written.
    assert not victim.exists()
