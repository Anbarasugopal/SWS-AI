from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import ROOT_DIR, get_settings
from app.rag.service import RAGService
from app.schemas import ChatRequest, ChatResponse, HealthResponse, SourceDocument


settings = get_settings()
rag_service = RAGService(settings)

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = ROOT_DIR / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(static_dir / "index.html")


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    chunk_count = rag_service.chunk_count()
    return HealthResponse(
        status="ready" if chunk_count else "empty",
        collection=settings.collection_name,
        chunk_count=chunk_count,
        retrieval_k=settings.retrieval_k,
    )


@app.get("/api/sources", response_model=list[SourceDocument])
def sources() -> list[SourceDocument]:
    return [SourceDocument(**source) for source in rag_service.source_documents()]


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponse:
    if rag_service.chunk_count() == 0:
        raise HTTPException(
            status_code=503,
            detail="No documents have been ingested yet. Run: python scripts/ingest.py --reset",
        )

    answer, sources_used, chunks, provider = await rag_service.chat(request.question.strip())
    return ChatResponse(answer=answer, sources=sources_used, chunks=chunks, provider=provider)


@app.get("/{path:path}", include_in_schema=False)
def spa_fallback(path: str) -> FileResponse:
    requested = Path(path)
    if requested.suffix:
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(static_dir / "index.html")
