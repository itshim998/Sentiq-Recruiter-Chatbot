from pathlib import Path
import uuid

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_PDF_SIZE = 5 * 1024 * 1024   # 5 MB
MAX_TXT_SIZE = 1 * 1024 * 1024   # 1 MB

def save_upload(file_bytes: bytes, original_name: str) -> Path:
    ext = Path(original_name).suffix.lower()

    if ext == ".pdf" and len(file_bytes) > MAX_PDF_SIZE:
        raise ValueError("PDF exceeds 5 MB size limit")

    if ext == ".txt" and len(file_bytes) > MAX_TXT_SIZE:
        raise ValueError("TXT exceeds 1 MB size limit")

    if ext not in [".pdf", ".txt"]:
        raise ValueError("Unsupported file type")

    file_id = uuid.uuid4().hex
    path = UPLOAD_DIR / f"{file_id}{ext}"
    path.write_bytes(file_bytes)
    return path
