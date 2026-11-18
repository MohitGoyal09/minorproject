"""Create a text-free ("scanned-looking") copy of an invoice PDF.

The copy has no text layer, so it exercises the OCR path instead of the fast
PyMuPDF extraction. Use it to demo or test scanned-document support.

    python data/generators/make_scanned_copy.py \
        data/sample_invoices/INV-2026-001.pdf /tmp/scanned-invoice.pdf
"""

import sys

import pymupdf


def make_scanned_copy(source: str, destination: str, dpi: int = 200) -> None:
    original = pymupdf.open(source)
    output = pymupdf.open()
    for page in original:
        pixmap = page.get_pixmap(dpi=dpi)
        image_page = output.new_page(width=page.rect.width, height=page.rect.height)
        image_page.insert_image(image_page.rect, pixmap=pixmap)
    output.save(destination)
    original.close()
    output.close()


if __name__ == "__main__":
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    make_scanned_copy(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 200)
    print(f"Wrote {sys.argv[2]} (no text layer; OCR path)")
