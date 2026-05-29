from pathlib import Path
import re

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import ROOT_DIR, get_settings
from app.rag.service import RAGService
from app.schemas import ChatRequest, ChatResponse, HealthResponse, SourceDocument, UploadResponse


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


@app.post("/api/documents", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    filename = safe_pdf_filename(file.filename or "")
    if not filename:
        raise HTTPException(status_code=400, detail="Upload a PDF file.")

    settings.pdf_dir.mkdir(parents=True, exist_ok=True)
    destination = settings.pdf_dir / filename
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="The uploaded PDF is empty.")
    destination.write_bytes(content)

    try:
        result = rag_service.ingest_pdf(destination)
    except Exception as exc:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=f"Could not ingest PDF: {exc}") from exc

    return UploadResponse(**result)


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


def safe_pdf_filename(filename: str) -> str | None:
    name = Path(filename).name.strip()
    if not name.lower().endswith(".pdf"):
        return None
    sanitized = re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip(".-")
    if not sanitized or sanitized.lower() == ".pdf":
        return None
    return sanitized
