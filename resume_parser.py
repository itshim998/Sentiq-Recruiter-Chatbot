from pathlib import Path
import pdfplumber
import pytesseract
from PIL import Image
import io

def extract_text_from_txt(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8", errors="ignore").strip()

def extract_text_from_pdf(file_path: Path) -> str:
    text = ""

    # 1️⃣ Try text-based PDF extraction
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

    if text.strip():
        return text.strip()

    # 2️⃣ OCR fallback for scanned PDFs
    with pdfplumber.open(file_path) as pdf:
        for page in pdf.pages:
            image = page.to_image(resolution=300).original
            ocr_text = pytesseract.image_to_string(image)
            text += ocr_text + "\n"

    return text.strip()

def parse_text_file(file_path: Path) -> str:
    if not file_path.exists():
        raise ValueError("File does not exist")

    suffix = file_path.suffix.lower()

    if suffix == ".txt":
        return extract_text_from_txt(file_path)

    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)

    raise ValueError("Unsupported resume format")
