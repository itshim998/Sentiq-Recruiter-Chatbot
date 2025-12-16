from pathlib import Path

def parse_text_file(file_path: Path) -> str:
    if not file_path.exists():
        raise ValueError("File does not exist")

    if file_path.suffix.lower() != ".txt":
        raise ValueError("Only .txt files are supported")

    content = file_path.read_text(encoding="utf-8", errors="ignore")
    return content.strip()
