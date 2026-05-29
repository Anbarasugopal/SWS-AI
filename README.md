# SWS AI RAG Policy Chatbot

A Python RAG chatbot for answering employee questions from the 10 SWS AI company policy PDFs. The app includes:

- PDF ingestion with PyMuPDF
- 500 character chunks with 50 character overlap
- Qdrant local mode as the persistent vector database
- FastAPI backend with `POST /api/chat`
- A white and blue Livvic chat UI served by the backend
- Source documents and pages returned with every answer
- PDF upload from the UI with immediate indexing into the vector store

## Project Structure

```text
app/
  main.py              FastAPI app and API routes
  rag/                 PDF loading, chunking, vector store, LLM, RAG service
static/                Chat UI
scripts/ingest.py      Builds the Qdrant index from PDFs
scripts/query.py       CLI smoke test for retrieval and answering
data/pdfs/             SWS AI PDF documents
storage/qdrant/        Generated Qdrant vector database, ignored by git
```

## Setup

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

If you want LLM generation, add one provider key to `.env`:

```bash
OPENAI_API_KEY=your_key
LLM_PROVIDER=openai
```

You can also use Anthropic (`ANTHROPIC_API_KEY`, `LLM_PROVIDER=anthropic`) or Ollama (`LLM_PROVIDER=ollama`, `OLLAMA_MODEL=llama3.1`). If no provider is configured, the app uses a local extractive fallback so the retrieval pipeline and UI still run.

## Ingest Documents

```bash
python scripts/ingest.py --reset
```

This loads all PDFs from `data/pdfs`, extracts page text, chunks it, embeds each chunk with FastEmbed's local all-MiniLM-L6-v2 embedding model, and stores the vectors plus metadata in `storage/qdrant`.

## Run the App

```bash
uvicorn app.main:app --reload --port 8000
```

Open [http://localhost:8000](http://localhost:8000).

## API

```http
POST /api/chat
Content-Type: application/json

{
  "question": "How many days of sick leave do employees get?"
}
```

Upload and index a new PDF:

```http
POST /api/documents
Content-Type: multipart/form-data

file=@your-policy.pdf
```

Uploaded PDFs are saved into `data/pdfs`. If a file with the same name already exists, its old chunks are removed from Qdrant before the replacement is indexed.

Response:

```json
{
  "answer": "Employees get ...",
  "sources": [
    {
      "document": "SWS-AI-leave-policy.pdf",
      "title": "SWS AI Leave Policy",
      "page": 1,
      "chunk_index": 2,
      "score": 0.82
    }
  ],
  "chunks": [],
  "provider": "openai"
}
```

## Architecture Decisions

**Vector DB:** Qdrant local mode is used because it runs locally, persists to disk, needs no external service, and avoids Windows compiler issues during setup.

**Embedding model:** FastEmbed uses the local `sentence-transformers/all-MiniLM-L6-v2` model. It keeps setup simple and avoids requiring an embedding API key. The metadata stored with each vector includes source file, display title, page number, and chunk index.

**Chunking:** Text is extracted page by page with PyMuPDF and split into 500 character chunks with 50 characters of overlap. This is small enough for precise policy lookup while preserving enough surrounding context for answer generation.

**Retrieval k:** The API retrieves the top 4 chunks by cosine similarity. This balances coverage across policy documents with a compact context window.

**Prompt design:** The system prompt tells the LLM to answer only from the provided context and to return `I don't have that information in the company documents.` when the answer is not present. The API still returns the retrieved sources so the UI can show which documents grounded the answer.

## Sample Queries

Qdrant local mode opens the vector store in one process at a time. Run these CLI checks when the FastAPI server is stopped, or test the same questions through the web UI/API while the server is running.

```bash
python scripts/query.py "What is the annual leave policy at SWS AI?"
python scripts/query.py "How many days of sick leave do employees get?"
python scripts/query.py "What is the notice period for resignation?"
python scripts/query.py "What tools does SWS AI use for communication?"
python scripts/query.py "What is the password policy for company systems?"
python scripts/query.py "How are performance reviews conducted?"
python scripts/query.py "What are the WFH guidelines?"
python scripts/query.py "Does SWS AI offer health insurance?"
```
