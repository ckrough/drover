"""Integration test: Docling OCR on a synthetic scanned PDF (prof-kjg).

The 80-doc eval corpus is 100% born-digital, so it cannot exercise
Docling's OCR fallback. This test builds a privacy-safe, image-only
PDF at runtime (PIL renders text to a PNG, then saves the PNG as a
single-page PDF — no embedded text layer) and asserts:

  1. The current `unstructured` loader cannot recover text — either
     because PDF support is missing (no poppler) or because there is
     no text layer to partition.
  2. The new `DoclingLoader` extracts the rendered text via OCR.

OCR engine: Docling defaults to RapidOCR (ONNX runtime, MIT-licensed,
verified working on macOS arm64). On first run, RapidOCR downloads
~15 MB of detection / classification / recognition ONNX models into
the docling extra's site-packages. Subsequent runs are offline.

Opt-in only: set `DROVER_RUN_OCR_TEST=1` to run. Default `pytest`
runs skip these tests because they need network on first invocation
and a sufficiently complete `unstructured[pdf]` install to compare
fairly.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

from drover.loader import DoclingLoader, DocumentLoader, DocumentLoadError

if TYPE_CHECKING:
    from pathlib import Path


_OCR_TEST_ENABLED = os.environ.get("DROVER_RUN_OCR_TEST") == "1"


pytestmark = pytest.mark.skipif(
    not _OCR_TEST_ENABLED,
    reason=(
        "Set DROVER_RUN_OCR_TEST=1 to run the OCR scanned-PDF test; "
        "first run downloads ~15 MB of RapidOCR ONNX models."
    ),
)


SCAN_TEXT_LINES = [
    "INVOICE",
    "From: Bridgeport Telecom",
    "Date: 2025-11-15",
    "Bill To: Acme Corp",
    "Amount Due: 250 USD",
]


def _build_image_only_pdf(target: Path) -> None:
    """Render `SCAN_TEXT_LINES` to a PNG and save as a single-page PDF.

    The resulting PDF has no text layer. `pdftotext` / `unstructured`
    cannot recover the text; OCR is the only path.
    """
    from PIL import Image, ImageDraw, ImageFont

    width, height = 1700, 2200  # ~Letter at 200 dpi
    img = Image.new("RGB", (width, height), color="white")
    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", size=64)
    except OSError:
        font = ImageFont.load_default()

    y = 200
    for line in SCAN_TEXT_LINES:
        draw.text((200, y), line, fill="black", font=font)
        y += 120

    img.save(target, "PDF", resolution=200.0)


@pytest.mark.integration
async def test_unstructured_loader_returns_empty_on_image_only_pdf(
    tmp_path: Path,
) -> None:
    """Document the gap: `unstructured` cannot read scanned PDFs without OCR."""
    pdf_path = tmp_path / "scanned_invoice.pdf"
    _build_image_only_pdf(pdf_path)

    loader = DocumentLoader()

    try:
        loaded = await loader.load(pdf_path)
    except DocumentLoadError:
        # Any DocumentLoadError is fair evidence of the gap — the loader
        # could not turn the scanned PDF into useful text. This includes
        # both "No text content" (parsed but empty) and the
        # "Unable to get page count. Is poppler installed and in PATH?"
        # signature seen on macOS without poppler.
        return

    # If extraction succeeded, the content must be near-empty (no real text
    # tokens recovered from the image).
    text = loaded.content.strip()
    assert len(text) < 20, (
        f"Expected near-empty content from unstructured on image-only PDF, "
        f"got {len(text)} chars: {text!r}"
    )


@pytest.mark.integration
async def test_docling_loader_recovers_text_via_ocr(tmp_path: Path) -> None:
    """Docling's OCR pipeline recovers the rendered text."""
    pdf_path = tmp_path / "scanned_invoice.pdf"
    _build_image_only_pdf(pdf_path)

    loader = DoclingLoader()
    loaded = await loader.load(pdf_path)

    content_lower = loaded.content.lower()
    # Tolerate OCR noise on individual characters but require a couple of
    # signal phrases to come through.
    hits = sum(
        keyword in content_lower
        for keyword in ("invoice", "bridgeport", "acme", "2025")
    )
    assert hits >= 2, f"OCR recovered too little signal: {loaded.content!r}"
    assert loaded.loader_backend == "docling"
