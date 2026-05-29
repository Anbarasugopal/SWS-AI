from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.rag.documents import load_pdf_chunks
from app.rag.vector_store import QdrantVectorStore


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest SWS AI PDFs into local Qdrant.")
    parser.add_argument("--pdf-dir", type=Path, default=None, help="Directory containing PDF files.")
    parser.add_argument("--reset", action="store_true", help="Delete and rebuild the Qdrant collection.")
    parser.add_argument("--chunk-size", type=int, default=None, help="Chunk size in characters.")
    parser.add_argument("--chunk-overlap", type=int, default=None, help="Chunk overlap in characters.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = get_settings()
    pdf_dir = args.pdf_dir or settings.pdf_dir
    chunk_size = args.chunk_size or settings.chunk_size
    chunk_overlap = args.chunk_overlap or settings.chunk_overlap

    print(f"Loading PDFs from: {pdf_dir}")
    chunks = load_pdf_chunks(pdf_dir, chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    print(f"Extracted {len(chunks)} chunks from {len(list(pdf_dir.glob('*.pdf')))} PDFs")

    store = QdrantVectorStore(settings)
    if args.reset:
        print(f"Resetting collection: {settings.collection_name}")
        store.reset()
    elif store.count() > 0:
        print(
            f"Collection already has {store.count()} chunks. "
            "Use --reset to rebuild it and avoid duplicate IDs."
        )
        return 1

    store.add_chunks(chunks)
    print(f"Stored {store.count()} chunks in Qdrant at: {settings.qdrant_dir}")

    sample_query = "What is the leave policy?"
    results = store.query(sample_query, k=3)
    print(f"\nSample retrieval: {sample_query}")
    for index, result in enumerate(results, start=1):
        metadata = result.metadata
        print(
            f"{index}. {metadata.get('document_title')} "
            f"(page {metadata.get('page')}, distance={result.distance:.4f})"
        )
        print(f"   {result.text[:180].replace(chr(10), ' ')}...")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
