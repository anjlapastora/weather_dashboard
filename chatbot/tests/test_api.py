"""
tests/test_api.py — Unit tests for the FastAPI chatbot endpoints.

All tests use the fake_rag fixture (MagicMock) so no real LLM or
ChromaDB is needed. They verify request validation, response shape,
HTTP status codes, and error propagation.

Run:
    pytest chatbot/tests/test_api.py -v
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ── /health ───────────────────────────────────────────────────────────────────

class TestHealth:
    def test_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200

    def test_status_ok(self, client):
        body = client.get("/health").json()
        assert body["status"] == "ok"

    def test_returns_model_name(self, client):
        body = client.get("/health").json()
        assert "model" in body
        assert isinstance(body["model"], str)

    def test_returns_indexed_doc_count(self, client):
        body = client.get("/health").json()
        assert "indexed_docs" in body
        assert body["indexed_docs"] == 42  # matches fake_rag.doc_count


# ── /chat ─────────────────────────────────────────────────────────────────────

class TestChat:
    def test_valid_message_returns_200(self, client):
        r = client.post("/chat", json={"message": "What is Helios?"})
        assert r.status_code == 200

    def test_response_has_reply(self, client):
        body = client.post("/chat", json={"message": "What is Helios?"}).json()
        assert "reply" in body
        assert isinstance(body["reply"], str)
        assert len(body["reply"]) > 0

    def test_response_has_sources_list(self, client):
        body = client.post("/chat", json={"message": "What is Helios?"}).json()
        assert "sources" in body
        assert isinstance(body["sources"], list)

    def test_sources_contain_expected_file(self, client):
        body = client.post("/chat", json={"message": "anomaly"}).json()
        assert "anomaly_detection.md" in body["sources"]

    def test_reply_content_from_rag(self, client, fake_rag):
        fake_rag.query.return_value = ("Custom reply text.", ["overview.md"])
        body = client.post("/chat", json={"message": "hello"}).json()
        assert body["reply"] == "Custom reply text."

    def test_empty_message_returns_422(self, client):
        r = client.post("/chat", json={"message": ""})
        assert r.status_code == 422

    def test_missing_message_field_returns_422(self, client):
        r = client.post("/chat", json={})
        assert r.status_code == 422

    def test_message_too_long_returns_422(self, client):
        r = client.post("/chat", json={"message": "x" * 1001})
        assert r.status_code == 422

    def test_rag_exception_returns_502(self, client, fake_rag):
        fake_rag.query.side_effect = ConnectionRefusedError("Ollama not running")
        r = client.post("/chat", json={"message": "test"})
        assert r.status_code == 502

    def test_502_detail_mentions_ollama(self, client, fake_rag):
        fake_rag.query.side_effect = RuntimeError("connection refused")
        body = client.post("/chat", json={"message": "test"}).json()
        assert "Ollama" in body["detail"] or "LLM" in body["detail"]

    def test_rag_query_called_with_message(self, client, fake_rag):
        client.post("/chat", json={"message": "tell me about sites"})
        fake_rag.query.assert_called_once_with("tell me about sites")

    def test_non_json_body_returns_422(self, client):
        r = client.post("/chat", content="plain text", headers={"Content-Type": "text/plain"})
        assert r.status_code == 422


# ── /rebuild ──────────────────────────────────────────────────────────────────

class TestRebuild:
    def test_returns_200(self, client):
        r = client.post("/rebuild")
        assert r.status_code == 200

    def test_status_ok(self, client):
        body = client.post("/rebuild").json()
        assert body["status"] == "ok"

    def test_message_mentions_chunks(self, client):
        body = client.post("/rebuild").json()
        assert "chunk" in body["message"].lower() or "rebuilt" in body["message"].lower()

    def test_rebuild_called_on_rag(self, client, fake_rag):
        client.post("/rebuild")
        fake_rag.rebuild_index.assert_called_once()

    def test_rebuild_exception_returns_500(self, client, fake_rag):
        fake_rag.rebuild_index.side_effect = FileNotFoundError("knowledge dir missing")
        r = client.post("/rebuild")
        assert r.status_code == 500


# ── CORS headers ──────────────────────────────────────────────────────────────

class TestCORS:
    def test_cors_header_present_on_chat(self, client):
        r = client.post(
            "/chat",
            json={"message": "hello"},
            headers={"Origin": "http://localhost:8780"},
        )
        assert r.status_code == 200
        assert "access-control-allow-origin" in r.headers
