"""
Core PDF extraction engine.
Uses pdfplumber for text-based PDFs from Indian university result sheets.
"""
import tempfile
import os
import signal
from typing import Optional

import pdfplumber


MAX_PAGES = 500
PAGE_TIMEOUT_SECONDS = 10


def extract_pdf_text_from_bytes(content: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        return _extract_text(tmp_path)
    finally:
        os.unlink(tmp_path)


def _extract_text(pdf_path: str) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        if len(pdf.pages) > MAX_PAGES:
            raise ValueError(
                f"PDF has {len(pdf.pages)} pages (max {MAX_PAGES}). "
                "Please upload a smaller file."
            )

        for page in pdf.pages:
            try:
                page_text = page.extract_text(x_tolerance=3, y_tolerance=3)
                if page_text:
                    text_parts.append(page_text)
            except Exception:
                continue  # Skip pages that fail to parse
            text_parts.append("\f")

    full_text = "".join(text_parts)
    if len(full_text.strip()) < 50:
        raise ValueError(
            "Could not extract text from PDF. "
            "The file may be scanned/image-based or corrupted."
        )
    return full_text
