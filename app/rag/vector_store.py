from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from fastembed import TextEmbedding
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

from app.config import Settings
from app.rag.documents import DocumentChunk


@dataclass(frozen=True)
class RetrievalResult:
    text: str
    metadata: dict[str, Any]
    distance: float | None


class QdrantVectorStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        Path(settings.qdrant_dir).mkdir(parents=True, exist_ok=True)
        self.client = QdrantClient(path=str(settings.qdrant_dir))
        self.embedder = TextEmbedding(model_name=settings.embedding_model)
        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if self.client.collection_exists(self.settings.collection_name):
            return
        self.client.create_collection(
            collection_name=self.settings.collection_name,
            vectors_config=VectorParams(
                size=self.settings.embedding_dimensions,
                distance=Distance.COSINE,
            ),
        )

    def reset(self) -> None:
        if self.client.collection_exists(self.settings.collection_name):
            self.client.delete_collection(self.settings.collection_name)
        self._ensure_collection()

    def add_chunks(self, chunks: list[DocumentChunk], batch_size: int = 96) -> None:
        for start in range(0, len(chunks), batch_size):
            batch = chunks[start : start + batch_size]
            vectors = self._embed([chunk.text for chunk in batch])
            points = []
            for chunk, vector in zip(batch, vectors, strict=True):
                payload = {**chunk.metadata, "text": chunk.text, "chunk_id": chunk.id}
                points.append(
                    PointStruct(
                        id=str(uuid5(NAMESPACE_URL, chunk.id)),
                        vector=vector,
                        payload=payload,
                    )
                )
            self.client.upsert(
                collection_name=self.settings.collection_name,
                points=points,
            )

    def count(self) -> int:
        if not self.client.collection_exists(self.settings.collection_name):
            return 0
        return self.client.count(collection_name=self.settings.collection_name, exact=True).count

    def query(self, question: str, k: int) -> list[RetrievalResult]:
        if self.count() == 0:
            return []

        query_vector = self._embed([question])[0]
        candidate_limit = max(k * 6, 20)
        response = self.client.query_points(
            collection_name=self.settings.collection_name,
            query=query_vector,
            limit=candidate_limit,
            with_payload=True,
        )
        hits = response.points
        results = [
            RetrievalResult(
                text=str((hit.payload or {}).get("text", "")),
                metadata={key: value for key, value in (hit.payload or {}).items() if key != "text"},
                distance=1 - float(hit.score),
            )
            for hit in hits
        ]
        return self._rerank(question, results, k=k)[:k]

    def source_documents(self) -> list[dict[str, Any]]:
        if self.count() == 0:
            return []

        points, next_page = self.client.scroll(
            collection_name=self.settings.collection_name,
            limit=256,
            with_payload=True,
            with_vectors=False,
        )
        while next_page is not None:
            next_points, next_page = self.client.scroll(
                collection_name=self.settings.collection_name,
                limit=256,
                offset=next_page,
                with_payload=True,
                with_vectors=False,
            )
            points.extend(next_points)

        grouped: dict[str, dict[str, Any]] = {}
        for point in points:
            metadata = point.payload or {}
            if not metadata:
                continue
            document = str(metadata.get("source", "Unknown"))
            entry = grouped.setdefault(
                document,
                {
                    "document": document,
                    "title": str(metadata.get("document_title", document)),
                    "chunks": 0,
                    "pages": set(),
                },
            )
            entry["chunks"] += 1
            if metadata.get("page") is not None:
                entry["pages"].add(int(metadata["page"]))

        return [
            {
                "document": entry["document"],
                "title": entry["title"],
                "chunks": entry["chunks"],
                "pages": sorted(entry["pages"]),
            }
            for entry in sorted(grouped.values(), key=lambda item: item["title"])
        ]

    def _embed(self, texts: list[str]) -> list[list[float]]:
        return [embedding.tolist() for embedding in self.embedder.embed(texts)]

    def _rerank(self, question: str, results: list[RetrievalResult], k: int) -> list[RetrievalResult]:
        keywords = _keywords(question)
        if not keywords:
            return results

        def score(result: RetrievalResult) -> float:
            vector_score = 1 - float(result.distance or 0)
            searchable = (
                f"{result.metadata.get('document_title', '')} "
                f"{result.metadata.get('source', '')} "
                f"{result.text}"
            ).lower()
            lexical_score = sum(1 for keyword in keywords if keyword in searchable)
            return vector_score + (lexical_score * 0.25)

        ranked = sorted(results, key=score, reverse=True)
        top = ranked[0]
        top_document = top.metadata.get("source")
        top_title_hits = _keyword_hits(str(top.metadata.get("document_title", "")), keywords)
        top_text_hits = _keyword_hits(top.text, keywords)

        if top_document and (top_title_hits > 0 or top_text_hits >= 2):
            same_document = [result for result in ranked if result.metadata.get("source") == top_document]
            other_documents = [result for result in ranked if result.metadata.get("source") != top_document]
            if len(same_document) >= min(3, k):
                return same_document
            if len(same_document) >= 2:
                return same_document + other_documents

        return ranked


def _keywords(question: str) -> set[str]:
    stopwords = {
        "a",
        "an",
        "and",
        "are",
        "at",
        "ai",
        "company",
        "documents",
        "do",
        "does",
        "employees",
        "for",
        "get",
        "how",
        "i",
        "in",
        "is",
        "many",
        "of",
        "on",
        "policy",
        "sws",
        "the",
        "to",
        "what",
        "when",
        "with",
    }
    return {token for token in re.findall(r"[a-z0-9]+", question.lower()) if len(token) > 2 and token not in stopwords}


def _keyword_hits(text: str, keywords: set[str]) -> int:
    lowered = text.lower()
    return sum(1 for keyword in keywords if keyword in lowered)
