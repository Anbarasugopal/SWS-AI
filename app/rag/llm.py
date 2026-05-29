from __future__ import annotations

import os
import re

import httpx

from app.config import Settings
from app.rag.vector_store import RetrievalResult


NO_ANSWER = "I don't have that information in the company documents."


SYSTEM_PROMPT = """You are SWS AI's internal policy assistant.
Answer employees using only the provided company document context.
If the context does not contain the answer, reply exactly:
I don't have that information in the company documents.
Keep answers concise, specific, and practical. Do not invent policy details."""


def build_context(chunks: list[RetrievalResult], max_chars: int) -> str:
    blocks: list[str] = []
    used_chars = 0
    for index, chunk in enumerate(chunks, start=1):
        metadata = chunk.metadata
        block = (
            f"[{index}] Document: {metadata.get('document_title', metadata.get('source', 'Unknown'))}\n"
            f"File: {metadata.get('source', 'Unknown')}\n"
            f"Page: {metadata.get('page', 'Unknown')}\n"
            f"Content:\n{chunk.text.strip()}"
        )
        if used_chars + len(block) > max_chars:
            break
        blocks.append(block)
        used_chars += len(block)
    return "\n\n---\n\n".join(blocks)


def resolve_provider(settings: Settings) -> str:
    provider = settings.llm_provider.lower().strip()
    if provider != "auto":
        return provider
    if os.getenv("OPENAI_API_KEY"):
        return "openai"
    if os.getenv("ANTHROPIC_API_KEY"):
        return "anthropic"
    return "extractive"


async def generate_answer(question: str, chunks: list[RetrievalResult], settings: Settings) -> tuple[str, str]:
    provider = resolve_provider(settings)
    context = build_context(chunks, settings.max_context_chars)
    if not context:
        return NO_ANSWER, provider

    try:
        if provider == "openai":
            return await _generate_openai(question, context, settings), provider
        if provider == "anthropic":
            return await _generate_anthropic(question, context, settings), provider
        if provider == "ollama":
            return await _generate_ollama(question, context, settings), provider
    except Exception as exc:
        fallback = extractive_answer(question, chunks)
        return f"{fallback}\n\nLLM provider '{provider}' was unavailable: {exc}", "extractive"

    return extractive_answer(question, chunks), "extractive"


async def _generate_openai(question: str, context: str, settings: Settings) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=settings.openai_model,
        temperature=settings.llm_temperature,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
    )
    return response.choices[0].message.content.strip()


async def _generate_anthropic(question: str, context: str, settings: Settings) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    response = await client.messages.create(
        model=settings.anthropic_model,
        temperature=settings.llm_temperature,
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
    )
    return "".join(block.text for block in response.content if getattr(block, "type", "") == "text").strip()


async def _generate_ollama(question: str, context: str, settings: Settings) -> str:
    payload = {
        "model": settings.ollama_model,
        "stream": False,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        "options": {"temperature": settings.llm_temperature},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        response = await client.post(f"{settings.ollama_base_url.rstrip('/')}/api/chat", json=payload)
        response.raise_for_status()
    return response.json()["message"]["content"].strip()


def extractive_answer(question: str, chunks: list[RetrievalResult]) -> str:
    """Local fallback that quotes relevant sentences when no LLM is configured."""
    keywords = _keywords(question)
    if not chunks or not keywords:
        return NO_ANSWER

    candidate_sentences: list[tuple[int, str, str]] = []
    for chunk in chunks:
        title = str(chunk.metadata.get("document_title", chunk.metadata.get("source", "company documents")))
        for sentence in _segments(chunk.text):
            score = sum(1 for keyword in keywords if keyword in sentence.lower())
            if score:
                candidate_sentences.append((score, title, sentence))

    if not candidate_sentences:
        return NO_ANSWER

    candidate_sentences.sort(key=lambda item: item[0], reverse=True)
    specific_keywords = keywords - {"days", "leave", "policy", "employee", "employees"}
    selected = []
    seen = set()
    for _, title, sentence in candidate_sentences:
        cleaned = sentence.strip()
        lowered = cleaned.lower()
        if selected and specific_keywords and not any(keyword in lowered for keyword in specific_keywords):
            continue
        if len(cleaned) < 25 and not re.search(r"\d", cleaned):
            continue
        if len(cleaned) < 35 and not re.search(r"[\d.:]", cleaned):
            continue
        if lowered in seen:
            continue
        if any(lowered in existing.lower() for existing in seen):
            continue
        seen.add(lowered)
        selected.append(f"{cleaned} ({title})")
        if len(selected) == 3:
            break

    return " ".join(selected)


def _segments(text: str) -> list[str]:
    raw_lines = [line.strip(" -\t") for line in text.splitlines()]
    lines = [line for line in raw_lines if line and not line.lower().startswith("sws ai |")]
    segments: list[str] = []

    for index, line in enumerate(lines):
        if re.match(r"^[a-z]\s", line):
            continue
        parts = [part.strip() for part in re.split(r"(?<=[.!?])\s+", line) if part.strip()]
        for part in parts:
            segments.append(part)
        if len(line) <= 80 and not re.search(r"[.!?]$", line) and index + 1 < len(lines):
            next_line = lines[index + 1]
            if not re.match(r"^[a-z]\s", next_line):
                segments.append(f"{line} {next_line}")

    return segments


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
