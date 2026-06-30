"""
config.py — Pydantic v2 settings for the Helios chatbot service.

Override any value with environment variables prefixed HELIOS_CHAT_:
  HELIOS_CHAT_LLM_MODEL=mistral uvicorn app:app --port 8000
"""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

CHATBOT_DIR = Path(__file__).parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HELIOS_CHAT_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Ollama LLM ────────────────────────────────────────────────────────────
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        description="Base URL of the running Ollama server.",
    )
    llm_model: str = Field(
        default="llama3.2",
        description="Ollama model tag to use for generation.",
    )
    temperature: float = Field(
        default=0.2,
        ge=0.0,
        le=2.0,
        description="Sampling temperature — lower = more deterministic.",
    )

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = Field(
        default="all-MiniLM-L6-v2",
        description="sentence-transformers model name for document embeddings.",
    )

    # ── ChromaDB ──────────────────────────────────────────────────────────────
    chroma_dir: Path = Field(
        default=CHATBOT_DIR / "chroma_db",
        description="Directory where ChromaDB persists its index.",
    )
    collection_name: str = Field(
        default="helios_kb",
        description="ChromaDB collection name.",
    )

    # ── Retrieval ─────────────────────────────────────────────────────────────
    knowledge_dir: Path = Field(
        default=CHATBOT_DIR / "knowledge",
        description="Directory containing the markdown knowledge documents.",
    )
    top_k: int = Field(
        default=4,
        ge=1,
        le=20,
        description="Number of chunks retrieved per query.",
    )
    chunk_size: int = Field(
        default=600,
        ge=100,
        description="Target character count per document chunk.",
    )
    chunk_overlap: int = Field(
        default=80,
        ge=0,
        description="Overlap between consecutive chunks.",
    )

    # ── FastAPI ───────────────────────────────────────────────────────────────
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8000, ge=1024, le=65535)
    cors_origins: list[str] = Field(
        default=["*"],
        description="CORS allowed origins. Use ['*'] for local dev.",
    )


settings = Settings()
