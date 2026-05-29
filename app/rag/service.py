from app.config import Settings
from app.rag.documents import extract_pdf_chunks
from app.rag.llm import NO_ANSWER, generate_answer
from app.rag.vector_store import QdrantVectorStore, RetrievalResult
from app.schemas import RetrievedChunk, Source


class RAGService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.vector_store = QdrantVectorStore(settings)

    def chunk_count(self) -> int:
        return self.vector_store.count()

    def source_documents(self) -> list[dict]:
        return self.vector_store.source_documents()

    def ingest_pdf(self, pdf_path) -> dict:
        chunks = extract_pdf_chunks(
            pdf_path,
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
        )
        if not chunks:
            raise ValueError("No text chunks could be extracted from the PDF.")

        self.vector_store.delete_source(pdf_path.name)
        self.vector_store.add_chunks(chunks)
        document = next(
            source for source in self.source_documents() if source["document"] == pdf_path.name
        )
        return {
            "document": document,
            "chunk_count": len(chunks),
            "total_chunks": self.chunk_count(),
        }

    async def chat(self, question: str) -> tuple[str, list[Source], list[RetrievedChunk], str]:
        chunks = self.vector_store.query(question, k=self.settings.retrieval_k)
        if not chunks:
            return NO_ANSWER, [], [], "none"

        answer, provider = await generate_answer(question, chunks, self.settings)
        sources = unique_sources(chunks)
        api_chunks = [
            RetrievedChunk(
                text=chunk.text,
                source=source_from_chunk(chunk),
            )
            for chunk in chunks
        ]
        return answer, sources, api_chunks, provider


def source_from_chunk(chunk: RetrievalResult) -> Source:
    metadata = chunk.metadata
    return Source(
        document=str(metadata.get("source", "Unknown")),
        title=str(metadata.get("document_title", metadata.get("source", "Unknown"))),
        page=int(metadata["page"]) if metadata.get("page") is not None else None,
        chunk_index=int(metadata["chunk_index"]) if metadata.get("chunk_index") is not None else None,
        score=(1 - float(chunk.distance)) if chunk.distance is not None else None,
    )


def unique_sources(chunks: list[RetrievalResult]) -> list[Source]:
    seen: set[tuple[str, int | None]] = set()
    sources: list[Source] = []
    for chunk in chunks:
        source = source_from_chunk(chunk)
        key = (source.document, source.page)
        if key in seen:
            continue
        seen.add(key)
        sources.append(source)
    return sources
