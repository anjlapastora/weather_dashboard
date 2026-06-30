"""
tests/conftest.py — Shared pytest fixtures for the chatbot test suite.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

# ── Paths ──────────────────────────────────────────────────────────────────────

CHATBOT_DIR = Path(__file__).parent.parent
KNOWLEDGE_DIR = CHATBOT_DIR / "knowledge"


# ── Fake RAG fixture ───────────────────────────────────────────────────────────

@pytest.fixture
def fake_rag():
    """
    A MagicMock that satisfies the HeliosRAG interface.
    Tests that need a controllable chatbot response use this instead of
    spinning up a real LLM + ChromaDB.
    """
    rag = MagicMock()
    rag.doc_count = 42
    rag.query.return_value = (
        "Helios uses the IQR method for anomaly detection by default.",
        ["anomaly_detection.md"],
    )
    rag.rebuild_index.return_value = 42
    return rag


# ── FastAPI test client ────────────────────────────────────────────────────────

@pytest.fixture
def client(fake_rag):
    """
    TestClient with the RAG dependency overridden to avoid loading
    real models or hitting Ollama.
    """
    # Import here so sys.path is set correctly by the time we do it
    import sys
    sys.path.insert(0, str(CHATBOT_DIR))

    from app import app, get_rag

    app.dependency_overrides[get_rag] = lambda: fake_rag
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


# ── Minimal Settings fixture ───────────────────────────────────────────────────

@pytest.fixture
def test_settings(tmp_path):
    """
    Settings pointing at the real knowledge/ dir but a temp chroma_db,
    so RAG tests don't pollute the production index.
    """
    import sys
    sys.path.insert(0, str(CHATBOT_DIR))

    from config import Settings
    return Settings(
        knowledge_dir=KNOWLEDGE_DIR,
        chroma_dir=tmp_path / "chroma_db",
        embedding_model="all-MiniLM-L6-v2",
        llm_model="llama3.2",
    )


# ── Sample documents fixture ───────────────────────────────────────────────────

@pytest.fixture
def sample_docs(tmp_path):
    """
    Two minimal markdown files for testing doc loading / chunking
    without depending on the real knowledge/ directory.
    """
    (tmp_path / "doc_a.md").write_text(
        "# Helios Overview\nHelios is a solar and wind monitoring dashboard.\n"
        "It tracks three sites: Riyadh, Wellington, Manila.\n",
        encoding="utf-8",
    )
    (tmp_path / "doc_b.md").write_text(
        "# Anomaly Detection\nHelios uses the IQR method to detect outliers.\n"
        "Bounds are computed as Q1 - 1.5*IQR and Q3 + 1.5*IQR.\n",
        encoding="utf-8",
    )
    return tmp_path
