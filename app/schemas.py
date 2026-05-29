from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)


class Source(BaseModel):
    document: str
    title: str
    page: int | None = None
    chunk_index: int | None = None
    score: float | None = None


class RetrievedChunk(BaseModel):
    text: str
    source: Source


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    chunks: list[RetrievedChunk]
    provider: str


class HealthResponse(BaseModel):
    status: str
    collection: str
    chunk_count: int
    retrieval_k: int


class SourceDocument(BaseModel):
    document: str
    title: str
    chunks: int
    pages: list[int]
