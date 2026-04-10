import os
from typing import BinaryIO

ALLOWED_EXTENSIONS = {
    ".pdf", ".xlsx", ".xls", ".csv", ".docx", ".ods"
}

MIME_TYPES = {
    ".pdf": "application/pdf",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
    ".csv": "text/csv",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".ods": "application/vnd.oasis.opendocument.spreadsheet",
}

# Magic bytes for file type validation
MAGIC_BYTES = {
    ".pdf": b"%PDF",
    ".xlsx": b"PK\x03\x04",
    ".xls": b"\xd0\xcf\x11\xe0",
    ".docx": b"PK\x03\x04",
    ".ods": b"PK\x03\x04",
}

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB


def validate_file_extension(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(
            f"Unsupported file type: {ext}. "
            f"Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    return ext


def validate_file_size(size: int) -> None:
    if size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {size / 1024 / 1024:.1f}MB. "
            f"Maximum: {MAX_FILE_SIZE / 1024 / 1024:.0f}MB"
        )


def validate_magic_bytes(content: bytes, extension: str) -> bool:
    expected = MAGIC_BYTES.get(extension)
    if expected is None:
        return True  # CSV has no magic bytes
    return content[:len(expected)] == expected


def validate_upload(filename: str, content: bytes) -> str:
    ext = validate_file_extension(filename)
    validate_file_size(len(content))
    if not validate_magic_bytes(content, ext):
        raise ValueError(
            f"File content does not match extension {ext}. "
            "The file may be corrupted or misnamed."
        )
    return ext


def sanitize_filename(name: str) -> str:
    """Remove path traversal characters and limit length."""
    import re
    # Take only the basename (no directory traversal)
    name = os.path.basename(name)
    # Remove any non-alphanumeric chars except dots, hyphens, underscores, spaces
    name = re.sub(r'[^\w\s\-.]', '', name)
    return name[:255] if name else "unnamed_file"
