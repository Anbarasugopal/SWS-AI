import re


def normalize_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_text(text: str, chunk_size: int = 500, chunk_overlap: int = 50) -> list[str]:
    """Split text into readable chunks with a small character overlap."""
    normalized = normalize_text(text)
    if not normalized:
        return []
    if len(normalized) <= chunk_size:
        return [normalized]

    chunks: list[str] = []
    start = 0
    separators = ["\n\n", "\n", ". ", "; ", ", ", " "]

    while start < len(normalized):
        hard_end = min(start + chunk_size, len(normalized))
        window = normalized[start:hard_end]
        split_at = len(window)

        if hard_end < len(normalized):
            best = -1
            for separator in separators:
                pos = window.rfind(separator)
                if pos > best:
                    best = pos + len(separator)
            if best >= int(chunk_size * 0.45):
                split_at = best

        chunk = normalized[start : start + split_at].strip()
        if chunk:
            chunks.append(chunk)

        next_start = start + split_at
        if next_start >= len(normalized):
            break
        start = max(next_start - chunk_overlap, start + 1)

    return chunks
