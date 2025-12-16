from pathlib import Path
import uuid

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

def save_upload(file_bytes: bytes, original_name: str) -> Path:
    ext = Path(original_name).suffix.lower()

    if ext not in [".txt"]:
        raise ValueError("Unsupported file type")

    file_id = uuid.uuid4().hex
    path = UPLOAD_DIR / f"{file_id}{ext}"

    path.write_bytes(file_bytes)
    return path
