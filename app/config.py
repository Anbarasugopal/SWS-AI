from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    app_name: str = "SWS AI Policy Assistant"
    pdf_dir: Path = Field(default=ROOT_DIR / "data" / "pdfs", alias="PDF_DIR")
    qdrant_dir: Path = Field(default=ROOT_DIR / "storage" / "qdrant", alias="QDRANT_DIR")
    collection_name: str = Field(default="sws_ai_documents", alias="COLLECTION_NAME")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2",
        alias="EMBEDDING_MODEL",
    )
    embedding_dimensions: int = Field(default=384, alias="EMBEDDING_DIMENSIONS")
    chunk_size: int = Field(default=500, alias="CHUNK_SIZE")
    chunk_overlap: int = Field(default=50, alias="CHUNK_OVERLAP")
    retrieval_k: int = Field(default=4, alias="RETRIEVAL_K")
    max_context_chars: int = Field(default=7000, alias="MAX_CONTEXT_CHARS")

    llm_provider: str = Field(default="auto", alias="LLM_PROVIDER")
    llm_temperature: float = Field(default=0.1, alias="LLM_TEMPERATURE")
    openai_model: str = Field(default="gpt-4o-mini", alias="OPENAI_MODEL")
    anthropic_model: str = Field(default="claude-3-5-haiku-latest", alias="ANTHROPIC_MODEL")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")
    ollama_model: str = Field(default="llama3.1", alias="OLLAMA_MODEL")

    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    @field_validator("pdf_dir", "qdrant_dir", mode="before")
    @classmethod
    def resolve_repo_relative_paths(cls, value: str | Path) -> Path:
        path = Path(value)
        if not path.is_absolute():
            return ROOT_DIR / path
        return path


@lru_cache
def get_settings() -> Settings:
    return Settings()
