"""OCR fallback for scanned / image-only invoices (methodology stages 1-2).

The digital path reads the PDF text layer with PyMuPDF. When that layer has no
tabular content (a scan or a phone photo), this module rasterises each page,
runs OCR, and rebuilds layout-aware markdown so the existing table corrector and
heuristic extractor can work without knowing where the text came from.

Engine choice: RapidOCR (ONNX Runtime) installs from pip alone, with bundled
models and no system binary. Tesseract would need a separate OS install, which
breaks the one-command setup on Windows.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional, Sequence

from app.engine.table_corrector import TableLayoutCorrector

DEFAULT_DPI = 300

# Column labels used to decide whether an OCR row is a table header.
HEADER_KEYWORDS = (
    "description", "item", "particular", "goods", "service",
    "hsn", "sac", "qty", "quantity", "rate", "price",
    "amount", "total", "discount", "tax", "unit",
)

_AMOUNT_RE = re.compile(r"^(?:inr|rs\.?|₹)?\s*-?(?:\d{1,3}(?:,\d{3})*|\d+)(?:\.\d{1,2})?$", re.IGNORECASE)


class OcrUnavailableError(RuntimeError):
    """Raised when no OCR engine is installed but a scan must be read."""


@dataclass
class Word:
    """One OCR text box, in page pixel coordinates."""

    text: str
    x0: float
    y0: float
    x1: float
    y1: float
    confidence: float = 1.0

    @property
    def center_x(self) -> float:
        return (self.x0 + self.x1) / 2

    @property
    def center_y(self) -> float:
        return (self.y0 + self.y1) / 2

    @property
    def height(self) -> float:
        return abs(self.y1 - self.y0)


def _is_amount(text: str) -> bool:
    return bool(_AMOUNT_RE.match(text.strip()))


def _looks_like_header(cells: Sequence[str]) -> bool:
    if len(cells) < 3:
        return False
    joined = " ".join(cells).lower()
    numerics = sum(1 for cell in cells if _is_amount(cell))
    return numerics <= 1 and any(keyword in joined for keyword in HEADER_KEYWORDS)


def _looks_like_table_row(cells: Sequence[str]) -> bool:
    if len(cells) < 3:
        return False
    return sum(1 for cell in cells if _is_amount(cell)) >= 2


def _is_summary_row(cells: Sequence[str]) -> bool:
    text = " ".join(cells)
    return TableLayoutCorrector.is_summary_row([text]) and any(_is_amount(cell) for cell in cells)


def group_words_into_rows(words: Sequence[Word], tolerance: Optional[float] = None) -> List[List[Word]]:
    """Cluster OCR boxes into visual rows, ordered top-to-bottom, left-to-right."""
    ordered = sorted(words, key=lambda w: (w.center_y, w.x0))
    if not ordered:
        return []

    heights = sorted(w.height for w in ordered if w.height > 0)
    median_height = heights[len(heights) // 2] if heights else 12.0
    row_tolerance = tolerance if tolerance is not None else max(median_height * 0.6, 6.0)

    rows: List[List[Word]] = []
    current: List[Word] = [ordered[0]]
    anchor_y = ordered[0].center_y

    for item in ordered[1:]:
        if abs(item.center_y - anchor_y) <= row_tolerance:
            current.append(item)
        else:
            rows.append(sorted(current, key=lambda w: w.x0))
            current = [item]
            anchor_y = item.center_y

    rows.append(sorted(current, key=lambda w: w.x0))
    return rows


def _overlap(a: Word, b: Word) -> float:
    return max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))


def _align_to_header(header: Sequence[Word], row: Sequence[Word]) -> List[str]:
    """Place row cells into their header columns so empty cells stay empty.

    OCR often misses a narrow cell (a single-digit quantity). Assigning by
    horizontal overlap keeps every other value in the right column instead of
    silently shifting the row left.
    """
    cells: List[List[str]] = [[] for _ in header]
    for item in row:
        best_index = max(range(len(header)), key=lambda i: _overlap(header[i], item))
        if _overlap(header[best_index], item) <= 0:
            best_index = min(range(len(header)), key=lambda i: abs(header[i].center_x - item.center_x))
        cells[best_index].append(item.text.strip())
    return [" ".join(cell).strip() for cell in cells]


def _pipe(cells: Sequence[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def rows_to_markdown(rows: Sequence[Sequence[Word]]) -> str:
    """Turn OCR rows into markdown: prose lines for text, pipe tables for tables."""
    blocks: List[str] = []
    header: Optional[Sequence[Word]] = None

    for row in rows:
        if not row:
            continue
        cells = [item.text.strip() for item in row]
        if not any(cells):
            continue

        if header is None and _looks_like_header(cells):
            header = row
            blocks.append(_pipe(cells))
            blocks.append("|" + "|".join(["---"] * len(cells)) + "|")
            continue

        if _looks_like_table_row(cells):
            blocks.append(_pipe(_align_to_header(header, row) if header else cells))
        elif _is_summary_row(cells):
            blocks.append(_pipe(cells))
        else:
            blocks.append(" ".join(cells))

    return "\n".join(blocks)


def _normalise_engine_item(item) -> Optional[Word]:
    """Accept the box formats returned by RapidOCR, PaddleOCR and Tesseract shims."""
    if not item or len(item) < 2:
        return None

    box, payload = item[0], item[1]
    if isinstance(payload, (list, tuple)):
        text = str(payload[0])
        confidence = float(payload[1]) if len(payload) > 1 else 1.0
    else:
        text = str(payload)
        confidence = float(item[2]) if len(item) > 2 else 1.0

    if not text.strip():
        return None

    if len(box) == 4 and not isinstance(box[0], (list, tuple)):
        x0, y0, x1, y1 = (float(v) for v in box)
    else:
        xs = [float(point[0]) for point in box]
        ys = [float(point[1]) for point in box]
        x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)

    return Word(text=text, x0=x0, y0=y0, x1=x1, y1=y1, confidence=confidence)


class OcrService:
    """Rasterise a PDF and read it with RapidOCR."""

    _engine = None

    @classmethod
    def is_available(cls) -> bool:
        try:
            import rapidocr_onnxruntime  # noqa: F401
        except Exception:
            return False
        return True

    @classmethod
    def _get_engine(cls):
        if cls._engine is None:
            try:
                from rapidocr_onnxruntime import RapidOCR
            except Exception as exc:  # pragma: no cover - environment dependent
                raise OcrUnavailableError(
                    "Scanned document detected, but no OCR engine is installed. "
                    "Install it with: pip install rapidocr-onnxruntime"
                ) from exc
            cls._engine = RapidOCR()
        return cls._engine

    @staticmethod
    def _render_page_images(pdf_path: str, dpi: int):
        try:
            import pymupdf as fitz
        except ImportError:  # pragma: no cover - older PyMuPDF
            import fitz

        import numpy as np
        from PIL import Image

        with fitz.open(pdf_path) as document:
            for page in document:
                pixmap = page.get_pixmap(dpi=dpi)
                image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
                yield np.array(image)

    @classmethod
    def page_words(cls, image) -> List[Word]:
        result, _ = cls._get_engine()(image)
        words: List[Word] = []
        for item in result or []:
            word = _normalise_engine_item(item)
            if word is not None:
                words.append(word)
        return words

    @classmethod
    def pdf_to_markdown(cls, pdf_path: str, dpi: int = DEFAULT_DPI) -> str:
        """Read every page and return layout-aware markdown."""
        pages: List[str] = []
        for image in cls._render_page_images(pdf_path, dpi):
            pages.append(rows_to_markdown(group_words_into_rows(cls.page_words(image))))
        markdown = "\n\n".join(page for page in pages if page.strip())
        if not markdown.strip():
            raise OcrUnavailableError(
                f"OCR produced no text for '{pdf_path}'. The file may be blank or corrupt."
            )
        return markdown
