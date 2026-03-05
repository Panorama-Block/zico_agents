"""Utilities for processing file uploads (images & documents) in chat."""

from __future__ import annotations

import base64
import os
from typing import Any, Dict

IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".gif": "image/gif",
    ".webp": "image/webp",
}

DOCUMENT_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".md": "text/markdown",
    ".csv": "text/csv",
}

MAX_IMAGE_SIZE = 10 * 1024 * 1024     # 10 MB
MAX_DOCUMENT_SIZE = 20 * 1024 * 1024  # 20 MB


def get_file_mime_type(filename: str, content_type: str | None = None) -> str | None:
    """Detect MIME type from file extension, falling back to content_type header."""
    if filename:
        ext = os.path.splitext(filename.lower())[1]
        if ext in IMAGE_MIME_TYPES:
            return IMAGE_MIME_TYPES[ext]
        if ext in DOCUMENT_MIME_TYPES:
            return DOCUMENT_MIME_TYPES[ext]
    return content_type


def is_image(mime: str | None) -> bool:
    return mime is not None and mime in IMAGE_MIME_TYPES.values()


def is_document(mime: str | None) -> bool:
    return mime is not None and mime in DOCUMENT_MIME_TYPES.values()


def extract_text_from_pdf(content: bytes, max_pages: int = 50) -> str:
    """Extract text from a PDF using pdfplumber, with PyPDF2 fallback."""
    import io

    # Try pdfplumber first (better table/layout extraction)
    try:
        import pdfplumber
        pages_text: list[str] = []
        with pdfplumber.open(io.BytesIO(content)) as pdf:
            for i, page in enumerate(pdf.pages):
                if i >= max_pages:
                    pages_text.append(f"\n[... truncated at {max_pages} pages ...]")
                    break
                text = page.extract_text()
                if text:
                    pages_text.append(text)
        result = "\n".join(pages_text)
        if result.strip():
            return result
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: PyPDF2
    try:
        from PyPDF2 import PdfReader
        reader = PdfReader(io.BytesIO(content))
        pages_text = []
        for i, page in enumerate(reader.pages):
            if i >= max_pages:
                pages_text.append(f"\n[... truncated at {max_pages} pages ...]")
                break
            text = page.extract_text()
            if text:
                pages_text.append(text)
        result = "\n".join(pages_text)
        if result.strip():
            return result
    except ImportError:
        pass
    except Exception:
        pass

    return "[PDF text extraction failed — neither pdfplumber nor PyPDF2 available]"


def extract_text_from_document(content: bytes, mime: str) -> str:
    """Dispatch document text extraction based on MIME type."""
    if mime == "application/pdf":
        return extract_text_from_pdf(content)
    # Plain text family: txt, markdown, csv
    return content.decode("utf-8", errors="replace")


def encode_image_for_gemini(content: bytes, mime: str) -> Dict[str, Any]:
    """Encode image bytes to the Gemini multimodal content block format."""
    encoded = base64.b64encode(content).decode("utf-8")
    return {
        "type": "media",
        "data": encoded,
        "mime_type": mime,
    }
