"""
profile_parser.py
-----------------
ResumeIQ — Profile Input Parsing Layer

Responsibility:
- Accept raw user input (PDF / TXT / manual text)
- Extract readable text reliably
- Normalize and clean the content
- Return a safe, AI-ready profile text

NO AI logic
NO database logic
NO recruiter assumptions
"""

from pathlib import Path
import io
import re

import pdfplumber
import pytesseract
from PIL import Image


# ------------------------------
# Public API
# ------------------------------

def parse_profile_input(
    file_bytes: bytes | None = None,
    filename: str | None = None,
    manual_text: str | None = None
) -> str:
    """
    Unified entry point.

    Accepts:
    - Uploaded PDF/TXT (bytes + filename)
    - OR manually entered text

    Returns:
    - Cleaned, normalized profile text (string)

    Raises:
    - ValueError on invalid or empty input
    """

    if manual_text:
        text = _normalize_text(manual_text)
        _validate_text(text)
        return text

    if not file_bytes or not filename:
        raise ValueError("No input provided")

    suffix = Path(filename).suffix.lower()

    if suffix == ".pdf":
        text = _extract_text_from_pdf(file_bytes)
    elif suffix == ".txt":
        text = _extract_text_from_txt(file_bytes)
    else:
        raise ValueError("Unsupported file type. Only PDF or TXT allowed.")

    text = _normalize_text(text)
    _validate_text(text)
    return text


# ------------------------------
# TXT extraction
# ------------------------------

def _extract_text_from_txt(file_bytes: bytes) -> str:
    try:
        return file_bytes.decode("utf-8", errors="ignore")
    except Exception:
        raise ValueError("Failed to read TXT file")


# ------------------------------
# PDF extraction (text + OCR fallback)
# ------------------------------

def _extract_text_from_pdf(file_bytes: bytes) -> str:
    text = ""

    # 1️⃣ Try text-based extraction
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception:
        text = ""

    if text.strip():
        return text

    # 2️⃣ OCR fallback (scanned PDFs)
    try:
        with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
            for page in pdf.pages:
                image = page.to_image(resolution=300).original
                ocr_text = pytesseract.image_to_string(image)
                text += ocr_text + "\n"
    except Exception:
        pass

    return text


# ------------------------------
# Normalization & Cleaning
# ------------------------------

def _normalize_text(text: str) -> str:
    """
    Clean and normalize extracted text:
    - Normalize newlines
    - Remove excessive whitespace
    - Strip control characters
    """

    if not isinstance(text, str):
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove control characters
    text = re.sub(r"[\x00-\x08\x0B-\x1F\x7F]", "", text)

    # Collapse excessive newlines
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Collapse excessive spaces
    text = re.sub(r"[ \t]{2,}", " ", text)

    return text.strip()


# ------------------------------
# Validation
# ------------------------------

def _validate_text(text: str):
    """
    Lightweight validation.
    Ensures downstream AI has enough signal.
    """

    if not text or not isinstance(text, str):
        raise ValueError("Extracted profile text is empty")

    if len(text) < 5:
        raise ValueError("Profile text too short to process reliably")

    if len(text) > 100_000:
        raise ValueError("Profile text too long")


# ------------------------------
# Optional local test
# ------------------------------

if __name__ == "__main__":
    # Simple smoke test
    sample = """
    John Doe
    Computer Science Student

    Skills: Python, Machine Learning, Flask
    Projects: Resume Builder, Chatbot
    """

    parsed = parse_profile_input(manual_text=sample)
    print(parsed)
