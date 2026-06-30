"""
app.py — FastAPI server for the Helios RAG chatbot.

Endpoints:
    GET  /health    — liveness check
    POST /chat      — ask the chatbot a question
    POST /rebuild   — rebuild the ChromaDB index from knowledge docs

Start with:
    uvicorn app:app --host 0.0.0.0 --port 8000 --reload
"""

import logging
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import settings
from rag import HeliosRAG

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
)
log = logging.getLogger("helios.chatbot")

# ── Global RAG instance (initialised once on startup) ─────────────────────────

_rag: HeliosRAG | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _rag
    log.info("Starting Helios chatbot service…")
    try:
        _rag = HeliosRAG()
        log.info("RAG pipeline ready — %d chunks indexed", _rag.doc_count)
    except Exception as exc:
        log.error("Failed to initialise RAG pipeline: %s", exc)
        raise
    yield
    log.info("Shutting down chatbot service")


def get_rag() -> HeliosRAG:
    if _rag is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG pipeline is not initialised.",
        )
    return _rag


# ── FastAPI app ───────────────────────────────────────────────────────────────

app = FastAPI(
    title="Helios Chatbot API",
    description="RAG-powered Q&A assistant for the Helios Solar & Wind Dashboard.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ── Schemas ───────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        examples=["What anomaly detection method does Helios use?"],
    )


class ChatResponse(BaseModel):
    reply: str
    sources: list[str] = []


class HealthResponse(BaseModel):
    status: str
    model: str
    indexed_docs: int


class RebuildResponse(BaseModel):
    status: str
    message: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/health", response_model=HealthResponse, tags=["ops"])
async def health(rag: Annotated[HeliosRAG, Depends(get_rag)]):
    """Liveness + readiness check — verifies the RAG pipeline is up."""
    return HealthResponse(
        status="ok",
        model=settings.llm_model,
        indexed_docs=rag.doc_count,
    )


@app.post("/chat", response_model=ChatResponse, tags=["chat"])
async def chat(
    req: ChatRequest,
    rag: Annotated[HeliosRAG, Depends(get_rag)],
):
    """
    Ask the Helios assistant a question.

    The response is grounded in the knowledge documents; sources lists which
    files contributed to the answer.
    """
    log.info("Query: %r", req.message)
    try:
        reply, sources = rag.query(req.message)
    except Exception as exc:
        log.exception("RAG query failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"LLM error: {exc}. Is Ollama running with model '{settings.llm_model}'?",
        )
    log.info("Reply (%d chars) from sources: %s", len(reply), sources)
    return ChatResponse(reply=reply, sources=sources)


@app.post("/rebuild", response_model=RebuildResponse, tags=["ops"])
async def rebuild(rag: Annotated[HeliosRAG, Depends(get_rag)]):
    """
    Rebuild the ChromaDB vector index from the knowledge documents.

    Use this after adding or editing files in chatbot/knowledge/.
    Takes ~10–30 seconds depending on document count and hardware.
    """
    log.info("Rebuilding index…")
    try:
        count = rag.rebuild_index()
    except Exception as exc:
        log.exception("Rebuild failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        )
    msg = f"Index rebuilt from {count} chunks"
    log.info(msg)
    return RebuildResponse(status="ok", message=msg)
