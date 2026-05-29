from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path

import fitz

from app.rag.splitter import split_text


@dataclass(frozen=True)
class DocumentChunk:
    id: str
    text: str
    metadata: dict[str, str | int]


def title_from_filename(filename: str) -> str:
    stem = Path(filename).stem
    words = stem.replace("SWS-AI-", "").replace("-", " ").split()
    return "SWS AI " + " ".join(word.capitalize() for word in words)


def extract_pdf_chunks(pdf_path: Path, chunk_size: int, chunk_overlap: int) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    document_title = title_from_filename(pdf_path.name)

    with fitz.open(pdf_path) as pdf:
        for page_index, page in enumerate(pdf, start=1):
            page_text = page.get_text("text")
            page_chunks = split_text(page_text, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
            for page_chunk_index, text in enumerate(page_chunks):
                digest = sha1(f"{pdf_path.name}:{page_index}:{page_chunk_index}:{text}".encode("utf-8")).hexdigest()
                chunk_index = len(chunks)
                chunks.append(
                    DocumentChunk(
                        id=f"{pdf_path.stem}-{page_index}-{page_chunk_index}-{digest[:12]}",
                        text=text,
                        metadata={
                            "source": pdf_path.name,
                            "document_title": document_title,
                            "page": page_index,
                            "chunk_index": chunk_index,
                            "page_chunk_index": page_chunk_index,
                        },
                    )
                )

    return chunks


def load_pdf_chunks(pdf_dir: Path, chunk_size: int, chunk_overlap: int) -> list[DocumentChunk]:
    pdf_paths = sorted(pdf_dir.glob("*.pdf"))
    if not pdf_paths:
        raise FileNotFoundError(f"No PDF files found in {pdf_dir}")

    chunks: list[DocumentChunk] = []
    for pdf_path in pdf_paths:
        chunks.extend(extract_pdf_chunks(pdf_path, chunk_size=chunk_size, chunk_overlap=chunk_overlap))
    return chunks
