from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.rag.service import RAGService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ask the local RAG service from the command line.")
    parser.add_argument("question", help="Question to ask.")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    settings = get_settings()
    try:
        service = RAGService(settings)
    except RuntimeError as exc:
        print(f"Could not open the local vector store: {exc}")
        print("If the FastAPI server is running, use /api/chat or stop the server before running this CLI.")
        return 1
    answer, sources, _, provider = await service.chat(args.question)

    print(f"Provider: {provider}")
    print(f"Answer: {answer}")
    print("Sources:")
    for source in sources:
        page = f", page {source.page}" if source.page else ""
        print(f"- {source.title}{page}")
    service.vector_store.client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
