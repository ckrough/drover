"""Derive structured regions from a parsed Docling document.

Walks `DoclingDocument.tables` and emits one region per row with
`label` set to the first cell text and `text` set to the remaining
cell text. This is the simplest mapping that lets metadata extractors
target named fields (e.g., "Bill To", "Issue Date") without parsing
table layouts in full.
"""

from __future__ import annotations

from typing import Any

from drover.extractors.base import StructuredRegion


def extract_structured_regions(docling_doc: Any) -> list[StructuredRegion]:
    """Flatten a `DoclingDocument` into label/text region pairs.

    Currently emits one region per non-trivial table row. Heading and
    paragraph extraction can be added later if metadata-extraction
    accuracy needs them.

    Args:
        docling_doc: A parsed `DoclingDocument` (or any object exposing
            a `.tables` iterable of `TableData`-shaped objects).

    Returns:
        List of `StructuredRegion` dicts. Empty when the document has
        no tables.
    """
    if docling_doc is None:
        return []

    regions: list[StructuredRegion] = []

    tables = getattr(docling_doc, "tables", None) or []
    for table in tables:
        for row in _iter_table_rows(table):
            cells = [str(cell).strip() for cell in row if str(cell).strip()]
            if len(cells) < 2:
                continue
            label, *rest = cells
            regions.append(
                StructuredRegion(
                    type="table_row",
                    label=label,
                    text=" ".join(rest),
                )
            )

    return regions


def _iter_table_rows(table: Any) -> list[list[Any]]:
    """Best-effort iterator over a Docling table's rows.

    Handles two shapes seen in the wild:
      1. `table.data.grid` — a 2D list of cell objects, each with `.text`.
      2. `table.data.table_cells` — a flat list of cells with row/col
         indices that we group into rows.
    """
    data = getattr(table, "data", None)
    if data is None:
        return []

    grid = getattr(data, "grid", None)
    if grid:
        return [[_cell_text(cell) for cell in row] for row in grid]

    cells = getattr(data, "table_cells", None)
    if cells:
        rows: dict[int, dict[int, str]] = {}
        for cell in cells:
            row_idx = getattr(cell, "start_row_offset_idx", None)
            col_idx = getattr(cell, "start_col_offset_idx", None)
            if row_idx is None or col_idx is None:
                continue
            rows.setdefault(row_idx, {})[col_idx] = _cell_text(cell)
        return [[rows[r][c] for c in sorted(rows[r])] for r in sorted(rows) if rows[r]]

    return []


def _cell_text(cell: Any) -> str:
    """Extract text from a Docling table cell (or fall back to str())."""
    text = getattr(cell, "text", None)
    if text is not None:
        return str(text)
    return str(cell)
