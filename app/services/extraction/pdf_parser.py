"""
Core PDF extraction engine.
Uses pdfplumber as primary, with subprocess pdftotext as fallback.
Handles text-based PDFs from Indian university result sheets.
"""

import re
import subprocess
import tempfile
import os
from typing import Optional

import pdfplumber


def extract_text_pdfplumber(pdf_path: str) -> str:
    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(
                x_tolerance=3,
                y_tolerance=3,
            )
            if page_text:
                text_parts.append(page_text)
            text_parts.append("\f")  # Form feed between pages
    return "".join(text_parts)


def extract_text_pdftotext(pdf_path: str) -> Optional[str]:
    try:
        result = subprocess.run(
            ["pdftotext", "-layout", pdf_path, "-"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return None


def extract_pdf_text(pdf_path: str) -> str:
    # Try pdftotext first (faster, preserves layout better)
    text = extract_text_pdftotext(pdf_path)
    if text and len(text.strip()) > 50:
        return text

    # Fallback to pdfplumber
    text = extract_text_pdfplumber(pdf_path)
    if text and len(text.strip()) > 50:
        return text

    raise ValueError(
        "Could not extract text from PDF. "
        "The file may be scanned/image-based or corrupted."
    )


def extract_pdf_text_from_bytes(content: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(content)
        tmp_path = tmp.name
    try:
        return extract_pdf_text(tmp_path)
    finally:
        os.unlink(tmp_path)
