def validate_text_field(text: str, name: str, min_len=20, max_len=20_000):
    if not isinstance(text, str):
        raise ValueError(f"{name} must be a string")

    stripped = text.strip()
    if len(stripped) < min_len:
        raise ValueError(f"{name} is too short")

    if len(stripped) > max_len:
        raise ValueError(f"{name} is too long")

    return stripped

