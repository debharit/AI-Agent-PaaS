

import argparse
import sys
import unicodedata
from pathlib import Path

# Characters that show up in extracted PDF text and help nothing.
JUNK_CHARS = {
    "­": "",  # soft hyphen
    "​": "",  # zero-width space
    "﻿": "",  # byte-order mark
    "\xa0": " ",  # non-breaking space
}

THAI_RANGE = range(0x0E00, 0x0E80)


def clean(text: str) -> str:
    """Normalise Unicode and strip characters that only cause trouble."""
    for bad, good in JUNK_CHARS.items():
        text = text.replace(bad, good)

    # Thai combines base characters with vowel and tone marks. NFC composes
    # them consistently, so searching and comparing text actually works.
    text = unicodedata.normalize("NFC", text)

    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def thai_ratio(text: str) -> float:
    """Fraction of non-space characters that are Thai."""
    chars = [c for c in text if not c.isspace()]
    if not chars:
        return 0.0

    return sum(ord(c) in THAI_RANGE for c in chars) / len(chars)


def extract_text_layer(pdf_path: Path) -> str:
    """Read the text the PDF already contains."""
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("pypdf is not installed. Run: pip install pypdf")

    reader = PdfReader(str(pdf_path))
    pages = []

    for number, page in enumerate(reader.pages, start=1):
        print(f"  page {number}/{len(reader.pages)}", end="\r", flush=True)
        pages.append(page.extract_text() or "")

    print(" " * 40, end="\r")
    return "\n\n".join(pages)


def render_pages(pdf_path: Path, dpi: int) -> list:
    """
    Render each page to a PIL image.

    Prefers PyMuPDF, which is a plain pip install. Falls back to pdf2image,
    which needs the poppler-utils system package.
    """
    try:
        import pymupdf
    except ImportError:
        pymupdf = None

    if pymupdf is not None:
        import io

        from PIL import Image

        document = pymupdf.open(str(pdf_path))
        return [
            Image.open(io.BytesIO(page.get_pixmap(dpi=dpi).tobytes("png")))
            for page in document
        ]

    try:
        from pdf2image import convert_from_path
    except ImportError:
        sys.exit(
            "OCR needs a way to render pages. Easiest:\n"
            "    pip install pymupdf"
        )

    return convert_from_path(str(pdf_path), dpi=dpi)


def extract_with_ocr(pdf_path: Path, lang: str, dpi: int) -> str:
    """Render each page to an image and OCR it. For scanned PDFs."""
    try:
        import pytesseract
    except ImportError:
        sys.exit(
            "OCR needs extra packages:\n"
            "    pip install pytesseract pymupdf\n"
            "    sudo apt-get update && sudo apt-get install -y tesseract-ocr tesseract-ocr-tha"
        )

    print(f"  rendering pages at {dpi} dpi (this is slow)...")
    images = render_pages(pdf_path, dpi)
    pages = []

    for number, image in enumerate(images, start=1):
        print(f"  OCR page {number}/{len(images)}", end="\r", flush=True)
        pages.append(pytesseract.image_to_string(image, lang=lang))

    print(" " * 40, end="\r")
    return "\n\n".join(pages)


def segment_thai_words(text: str) -> str:
    """Insert spaces between Thai words."""
    try:
        from pythainlp.tokenize import word_tokenize
    except ImportError:
        sys.exit("Word segmentation needs pythainlp. Run: pip install pythainlp")

    lines = []
    for line in text.splitlines():
        lines.append(" ".join(word_tokenize(line, keep_whitespace=False)) if line.strip() else "")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert a PDF to plain text (Thai-aware).")
    parser.add_argument("pdf", type=Path, help="the PDF to convert")
    parser.add_argument("-o", "--output", type=Path, help="output file (default: alongside the PDF)")
    parser.add_argument("--ocr", action="store_true", help="OCR the pages instead of reading the text layer")
    parser.add_argument("--lang", default="tha+eng", help="OCR languages (default: tha+eng)")
    parser.add_argument("--dpi", type=int, default=300, help="OCR render resolution (default: 300)")
    parser.add_argument("--words", action="store_true", help="insert spaces between Thai words")
    args = parser.parse_args()

    if not args.pdf.is_file():
        sys.exit(f"File not found: {args.pdf}")

    if args.words:
        # Fail now rather than after minutes of OCR.
        try:
            import pythainlp  # noqa: F401
        except ImportError:
            sys.exit("Word segmentation needs pythainlp. Run: pip install pythainlp")

    print(f"Reading {args.pdf.name}")

    if args.ocr:
        text = extract_with_ocr(args.pdf, args.lang, args.dpi)
    else:
        text = extract_text_layer(args.pdf)

    text = clean(text)

    if not text:
        sys.exit(
            "No text found. This PDF is probably a scan — re-run with --ocr:\n"
            f"    python {sys.argv[0]} {args.pdf} --ocr"
        )

    ratio = thai_ratio(text)

    if args.words:
        text = segment_thai_words(text)

    output = args.output or args.pdf.with_suffix(".txt")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text, encoding="utf-8")

    print(f"Wrote {output} — {len(text):,} characters, {ratio:.0%} Thai")

    # A PDF that should be Thai but extracts as almost none usually means the
    # embedded font has no usable character map, and OCR is the way out.
    if not args.ocr and ratio < 0.1:
        print(
            "\nWarning: hardly any Thai characters found.\n"
            "If the PDF looks Thai on screen, its fonts may not map to Unicode.\n"
            "Try: --ocr"
        )


if __name__ == "__main__":
    main()
