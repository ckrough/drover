# Implementation Plan: macOS Filesystem Tag Integration

## Overview

Add a new `drover tag` CLI command that classifies documents and applies macOS filesystem tags based on classification results. Design for extensibility so the future `drover rename` command shares the same architecture.

## Shared Architecture (Tag + Rename)

Both `tag` and `rename` commands follow the same pattern:
1. Classify files using existing `ClassificationService`
2. Apply an **action** to each file based on classification result
3. Support dry-run mode
4. Share CLI options for classification

```
┌─────────────────────────────────────────────────────────────────┐
│                     Shared Infrastructure                        │
├─────────────────────────────────────────────────────────────────┤
│  src/drover/actions/                                            │
│  ├── base.py          # FileAction protocol, ActionResult      │
│  ├── runner.py        # ActionRunner - orchestrates classify+act│
│  ├── tag.py           # TagAction implementation                │
│  └── rename.py        # RenameAction implementation (future)    │
└─────────────────────────────────────────────────────────────────┘

ActionRunner Flow:
──────────────────
drover tag/rename [OPTIONS] FILES...
    │
    ├─► ActionRunner.run(files, action, dry_run)
    │       │
    │       ├─► ClassificationService.classify_files()
    │       │       │
    │       │       └─► on_result callback
    │       │               │
    │       │               ├─► action.plan(file, result)  → ActionPlan
    │       │               ├─► if not dry_run:
    │       │               │       action.execute(plan)   → ActionResult
    │       │               └─► output result
    │       │
    │       └─► return exit_code
    │
    └─► Exit code (0/1/2)
```

## Core Abstractions

### FileAction Protocol

```python
# src/drover/actions/base.py

from typing import Protocol
from dataclasses import dataclass
from pathlib import Path
from drover.models import ClassificationResult

@dataclass
class ActionPlan:
    """What an action intends to do."""
    file: Path
    description: str           # Human-readable: "Add tags: financial, banking"
    changes: dict              # Action-specific details

@dataclass
class ActionResult:
    """Outcome of an executed action."""
    file: Path
    success: bool
    description: str
    changes: dict              # What actually changed
    error: str | None = None

class FileAction(Protocol):
    """Protocol for file actions based on classification."""

    def plan(self, file: Path, result: ClassificationResult) -> ActionPlan:
        """Plan what this action will do (for dry-run)."""
        ...

    def execute(self, plan: ActionPlan) -> ActionResult:
        """Execute the planned action."""
        ...
```

### ActionRunner

```python
# src/drover/actions/runner.py

class ActionRunner:
    """Orchestrates classification + action execution."""

    def __init__(self, config: DroverConfig, action: FileAction):
        self.service = ClassificationService(config)
        self.action = action

    async def run(
        self,
        files: list[Path],
        dry_run: bool = False,
        on_result: Callable[[ActionResult | ActionPlan], None] | None = None,
    ) -> int:
        """Classify files and apply action to each."""
        ...
```

## Tag-Specific Implementation

### TagAction

```python
# src/drover/actions/tag.py

class TagAction:
    """Action that applies macOS filesystem tags."""

    def __init__(
        self,
        fields: list[str],      # ["domain", "category", "doctype"]
        mode: TagMode,          # REPLACE, ADD, UPDATE, MISSING
    ):
        self.fields = fields
        self.mode = mode
        self.manager = TagManager()

    def plan(self, file: Path, result: ClassificationResult) -> ActionPlan:
        existing = self.manager.read_tags(file)
        new_tags = tags_from_result(result, self.fields)
        final = compute_final_tags(existing, new_tags, self.mode)

        added = [t for t in final if t not in existing]
        removed = [t for t in existing if t not in final]

        return ActionPlan(
            file=file,
            description=f"Add: {added}, Remove: {removed}" if added or removed else "No changes",
            changes={"existing": existing, "final": final, "added": added, "removed": removed},
        )

    def execute(self, plan: ActionPlan) -> ActionResult:
        try:
            self.manager.write_tags(plan.file, plan.changes["final"])
            return ActionResult(
                file=plan.file,
                success=True,
                description=plan.description,
                changes={"tags_added": plan.changes["added"], "tags_removed": plan.changes["removed"]},
            )
        except Exception as e:
            return ActionResult(file=plan.file, success=False, description="Failed", changes={}, error=str(e))
```

### TagManager (Low-level xattr operations)

```python
# src/drover/actions/tag.py (or separate tags.py)

class TagManager:
    """Manages macOS filesystem tags via xattr."""

    ATTR_NAME = "com.apple.metadata:_kMDItemUserTags"

    def read_tags(self, path: Path) -> list[str]: ...
    def write_tags(self, path: Path, tags: list[str]) -> None: ...
    def add_tags(self, path: Path, tags: list[str]) -> None: ...
    def remove_tags(self, path: Path, tags: list[str]) -> None: ...
```

## Future: RenameAction

```python
# src/drover/actions/rename.py (future)

class RenameAction:
    """Action that renames files based on classification."""

    def __init__(self, pattern: str, conflict: ConflictMode):
        self.pattern = pattern  # e.g., "{doctype}-{vendor}-{date}.{ext}"
        self.conflict = conflict  # SKIP, INCREMENT, OVERWRITE

    def plan(self, file: Path, result: ClassificationResult) -> ActionPlan:
        new_name = self._format_name(file, result)
        return ActionPlan(
            file=file,
            description=f"Rename to: {new_name}",
            changes={"old_name": file.name, "new_name": new_name, "new_path": file.parent / new_name},
        )

    def execute(self, plan: ActionPlan) -> ActionResult:
        # Handle conflicts, perform rename
        ...
```

## Tag Fields from Classification

| Field | Example Value | Tag Applied |
|-------|--------------|-------------|
| `domain` | `financial` | `financial` |
| `category` | `banking` | `banking` |
| `doctype` | `statement` | `statement` |
| `vendor` | `chase` | `chase` |
| `date` | `20240315` | `2024` (year only) |

Default: `domain,category,doctype`

**Example:** A bank statement gets tags: `financial`, `banking`, `statement`

## Tag Modes

| Mode | Description | Behavior |
|------|-------------|----------|
| `replace` | Replace all tags | Remove all existing tags, add new |
| `add` | Add tags, keep existing | Union of existing + new (default) |
| `update` | Update only if tagged | Only modify files that already have tags |
| `missing` | Add only to untagged | Add tags only if file has no existing tags |

## Implementation Phases

### Phase 1: Action Infrastructure

**Goal:** Create shared action abstractions that both `tag` and `rename` will use.

**Files to create:**
- `src/drover/actions/__init__.py`
- `src/drover/actions/base.py` - `FileAction` protocol, `ActionPlan`, `ActionResult`
- `src/drover/actions/runner.py` - `ActionRunner` class

**Features:**
- `FileAction` protocol with `plan()` and `execute()` methods
- `ActionPlan` dataclass for dry-run output
- `ActionResult` dataclass for execution results
- `ActionRunner` that wraps `ClassificationService` and applies actions

**Tests:**
- `tests/test_actions_base.py` - Test with mock action
- Test dry-run vs execute flow
- Test error handling

**Verification:** ActionRunner works with a simple mock action.

---

### Phase 2: TagManager (xattr operations)

**Goal:** Implement macOS tag read/write functionality.

**Files to create:**
- `src/drover/actions/tag.py` - `TagManager`, `TagMode`, helper functions

**Features:**
- `TagManager.read_tags(path) -> list[str]`
- `TagManager.write_tags(path, tags) -> None`
- `TagManager.add_tags(path, tags) -> None`
- `TagManager.remove_tags(path, tags) -> None`
- Binary plist serialization via `plistlib`
- Handle missing xattr gracefully

**Implementation details:**
- Use `xattr` library
- Attribute: `com.apple.metadata:_kMDItemUserTags`
- Tag format: `TagName\n0` (suffix = color index, 0 = no color)

**Tests:**
- `tests/test_tag_manager.py`
- Test read/write/add/remove operations
- Test empty file (no tags)
- Test binary plist format

**Verification:** Unit tests pass for all TagManager operations.

---

### Phase 3: TagAction + Tag Mapping

**Goal:** Implement `TagAction` that applies tags from classification.

**Files to modify:**
- `src/drover/actions/tag.py` - Add `TagAction`, `tags_from_result()`, `compute_final_tags()`

**Features:**
- `tags_from_result(result, fields) -> list[str]`
- `compute_final_tags(existing, new, mode) -> list[str]`
- `TagAction` implementing `FileAction` protocol
- All four tag modes

**Tag generation:**
```python
def tags_from_result(result: ClassificationResult, fields: list[str]) -> list[str]:
    tags = []
    for field in fields:
        if field == "date":
            tags.append(result.date[:4])  # Year only
        else:
            value = getattr(result, field, None)
            if value:
                tags.append(value)
    return tags
```

**Tests:**
- `tests/test_tag_action.py`
- Test tag generation from mock ClassificationResult
- Test all four modes
- Test plan() and execute() methods

**Verification:** TagAction works end-to-end with mocked classification.

---

### Phase 4: CLI Command + Shared Options

**Goal:** Add `drover tag` command with shared classification options.

**Files to modify:**
- `src/drover/cli.py` - Add `tag` command, extract shared options

**Shared options (decorator or function):**
```python
def classification_options(func):
    """Decorator applying common classification CLI options."""
    decorators = [
        click.option("--config", ...),
        click.option("--ai-provider", ...),
        click.option("--ai-model", ...),
        click.option("--taxonomy", ...),
        click.option("--taxonomy-mode", ...),
        click.option("--on-error", ...),
        click.option("--concurrency", ...),
        click.option("--log-level", ...),
    ]
    for decorator in reversed(decorators):
        func = decorator(func)
    return func
```

**Tag command:**
```
drover tag [OPTIONS] FILES...

Options:
  --tag-fields TEXT      Comma-separated fields (default: domain,category,doctype)
  --tag-mode [replace|add|update|missing]  (default: add)
  --dry-run              Show planned changes without applying

  # Shared classification options:
  --config, --ai-provider, --ai-model, --taxonomy, etc.
```

**Output format:**
```json
{"file": "invoice.pdf", "success": true, "tags_added": ["financial", "billing"], "tags_removed": []}
```

**Tests:**
- `tests/test_cli_tag.py`
- Test CLI help
- Test dry-run output
- Test with mock classifier

**Verification:** `drover tag --help` works, dry-run produces correct output.

---

### Phase 5: Integration + Polish

**Goal:** Full integration, error handling, edge cases.

**Features:**
- Platform detection (macOS only for tagging)
- Permission error handling
- Verbose/debug logging
- Handle files on non-HFS+/APFS filesystems

**Tests:**
- Integration test with temp files on macOS
- Test permission errors
- Test non-macOS platform behavior

**Edge cases:**
- Files without write permission
- Unicode in tags
- Very long tag lists

**Verification:** End-to-end test with real file tagging.

---

## Dependencies

**New dependency:**
```toml
dependencies = [
    # ... existing
    "xattr>=1.0.0",
]
```

## File Structure

```
src/drover/
├── actions/
│   ├── __init__.py      # Export public API
│   ├── base.py          # FileAction, ActionPlan, ActionResult
│   ├── runner.py        # ActionRunner
│   └── tag.py           # TagManager, TagAction, TagMode
├── cli.py               # Updated with tag command + shared options
└── ...existing files...
```

## Testing Strategy

- **Unit tests:** ActionRunner, TagManager, TagAction (mocked xattr for CI)
- **Integration tests:** Full pipeline with temp files (macOS only)
- **Skip on non-macOS:** `pytest.mark.skipif(sys.platform != "darwin")`

## Future Extensibility (Rename Command)

When implementing `drover rename`:

1. Create `src/drover/actions/rename.py` with `RenameAction`
2. Add CLI command in `cli.py` using same `classification_options` decorator
3. `RenameAction.plan()` computes new filename
4. `RenameAction.execute()` handles conflicts and performs rename
5. Reuse `ActionRunner` for orchestration

No changes needed to base infrastructure.
