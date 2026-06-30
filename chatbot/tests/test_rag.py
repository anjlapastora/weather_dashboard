"""
tests/test_rag.py — Unit tests for the HeliosRAG pipeline.

Strategy:
  - Document loading / chunking: uses real filesystem (sample_docs fixture)
  - Embedding + vector store: uses real sentence-transformers + in-memory Chroma
    (no Ollama needed for indexing)
  - LLM queries: Ollama is mocked so tests run without a running server

Run:
    pytest chatbot/tests/test_rag.py -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from config import Settings

KNOWLEDGE_DIR = Path(__file__).parent.parent / "knowledge"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_rag(cfg: Settings, llm_reply: str = "Test reply."):
    """
    Build a HeliosRAG with a mocked Ollama LLM that returns llm_reply.
    Embeddings and ChromaDB are real; only the LLM call is stubbed.
    """
    from rag import HeliosRAG

    mock_llm = MagicMock()
    mock_llm.invoke.return_value = llm_reply

    with patch("rag.OllamaLLM", return_value=mock_llm):
        rag = HeliosRAG(cfg=cfg)

    # Patch the LCEL chain to return {answer, context, question}
    rag.chain = MagicMock()
    rag.chain.invoke.return_value = {
        "answer": llm_reply,
        "context": [],
        "question": "",
    }
    return rag


# ── Document loading ──────────────────────────────────────────────────────────

class TestDocumentLoading:
    def test_knowledge_dir_has_md_files(self):
        md_files = list(KNOWLEDGE_DIR.glob("**/*.md"))
        assert len(md_files) >= 1, "No markdown files found in knowledge/"

    def test_load_docs_returns_list(self, test_settings):
        from rag import HeliosRAG
        with patch("rag.OllamaLLM"):
            rag = HeliosRAG(cfg=test_settings)
        docs = rag._load_docs()
        assert isinstance(docs, list)
        assert len(docs) > 0

    def test_each_doc_has_content(self, test_settings):
        from rag import HeliosRAG
        with patch("rag.OllamaLLM"):
            rag = HeliosRAG(cfg=test_settings)
        docs = rag._load_docs()
        for doc in docs:
            assert doc.page_content.strip(), "Document has empty page_content"

    def test_each_doc_has_source_metadata(self, test_settings):
        from rag import HeliosRAG
        with patch("rag.OllamaLLM"):
            rag = HeliosRAG(cfg=test_settings)
        docs = rag._load_docs()
        for doc in docs:
            assert "source" in doc.metadata

    def test_missing_knowledge_dir_raises(self, tmp_path):
        cfg = Settings(
            knowledge_dir=tmp_path / "nonexistent",
            chroma_dir=tmp_path / "chroma",
        )
        from rag import HeliosRAG
        with patch("rag.OllamaLLM"):
            with pytest.raises(FileNotFoundError):
                HeliosRAG(cfg=cfg)

    def test_empty_knowledge_dir_raises(self, tmp_path):
        empty_dir = tmp_path / "knowledge"
        empty_dir.mkdir()
        cfg = Settings(
            knowledge_dir=empty_dir,
            chroma_dir=tmp_path / "chroma",
        )
        from rag import HeliosRAG
        with patch("rag.OllamaLLM"):
            with pytest.raises(ValueError, match="No markdown documents found"):
                HeliosRAG(cfg=cfg)

    def test_sample_docs_load(self, sample_docs, tmp_path):
        cfg = Settings(
            knowledge_dir=sample_docs,
            chroma_dir=tmp_path / "chroma",
        )
        from rag import HeliosRAG
        with patch("rag.OllamaLLM"):
            rag = HeliosRAG(cfg=cfg)
        docs = rag._load_docs()
        assert len(docs) == 2


# ── Chunking ──────────────────────────────────────────────────────────────────

class TestChunking:
    def test_chunks_produced_from_sample_docs(self, sample_docs, tmp_path):
        cfg = Settings(
            knowledge_dir=sample_docs,
            chroma_dir=tmp_path / "chroma",
            chunk_size=200,
            chunk_overlap=20,
        )
        from rag import HeliosRAG
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        with patch("rag.OllamaLLM"):
            rag = HeliosRAG(cfg=cfg)
        docs = rag._load_docs()
        splitter = RecursiveCharacterTextSplitter(chunk_size=200, chunk_overlap=20)
        chunks = splitter.split_documents(docs)
        assert len(chunks) >= len(docs)

    def test_chunks_respect_size_limit(self, sample_docs, tmp_path):
        chunk_size = 150
        cfg = Settings(
            knowledge_dir=sample_docs,
            chroma_dir=tmp_path / "chroma",
            chunk_size=chunk_size,
            chunk_overlap=10,
        )
        from rag import HeliosRAG
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        with patch("rag.OllamaLLM"):
            rag = HeliosRAG(cfg=cfg)
        docs = rag._load_docs()
        splitter = RecursiveCharacterTextSplitter(chunk_size=chunk_size, chunk_overlap=10)
        chunks = splitter.split_documents(docs)
        # Most chunks should not dramatically exceed the target size
        oversized = [c for c in chunks if len(c.page_content) > chunk_size * 2]
        assert len(oversized) == 0


# ── Vector store ──────────────────────────────────────────────────────────────

class TestVectorStore:
    def test_doc_count_is_positive(self, test_settings):
        rag = _make_rag(test_settings)
        assert rag.doc_count > 0

    def test_doc_count_with_sample_docs(self, sample_docs, tmp_path):
        cfg = Settings(
            knowledge_dir=sample_docs,
            chroma_dir=tmp_path / "chroma",
        )
        rag = _make_rag(cfg)
        assert rag.doc_count >= 2

    def test_vectorstore_persists_to_disk(self, sample_docs, tmp_path):
        chroma_dir = tmp_path / "chroma"
        cfg = Settings(knowledge_dir=sample_docs, chroma_dir=chroma_dir)
        _make_rag(cfg)
        assert chroma_dir.exists()
        assert any(chroma_dir.iterdir())

    def test_load_existing_index_skips_rebuild(self, sample_docs, tmp_path):
        chroma_dir = tmp_path / "chroma"
        cfg = Settings(knowledge_dir=sample_docs, chroma_dir=chroma_dir)

        # Build once
        rag1 = _make_rag(cfg)
        count1 = rag1.doc_count

        # Load from disk — should not call _build_vectorstore again
        with patch("rag.HeliosRAG._build_vectorstore", wraps=None) as mock_build:
            rag2 = _make_rag(cfg)
            mock_build.assert_not_called()
        assert rag2.doc_count == count1


# ── Query ─────────────────────────────────────────────────────────────────────

class TestQuery:
    def test_query_returns_string_reply(self, test_settings):
        rag = _make_rag(test_settings, llm_reply="This is the answer.")
        reply, _ = rag.query("What is Helios?")
        assert isinstance(reply, str)
        assert reply == "This is the answer."

    def test_query_returns_sources_list(self, test_settings):
        rag = _make_rag(test_settings)
        _, sources = rag.query("What is Helios?")
        assert isinstance(sources, list)

    def test_query_invokes_chain(self, test_settings):
        rag = _make_rag(test_settings)
        rag.query("tell me about wind")
        # LCEL chain receives the plain question string, not a dict
        rag.chain.invoke.assert_called_once_with("tell me about wind")

    def test_sources_are_filenames_not_paths(self, test_settings):
        from langchain_core.documents import Document
        rag = _make_rag(test_settings)
        rag.chain.invoke.return_value = {
            "answer": "answer",
            "context": [
                Document(
                    page_content="x",
                    metadata={"source": "/some/path/overview.md"},
                )
            ],
            "question": "anything",
        }
        _, sources = rag.query("anything")
        assert all("/" not in s for s in sources)
        assert "overview.md" in sources

    def test_duplicate_sources_deduplicated(self, test_settings):
        from langchain_core.documents import Document
        rag = _make_rag(test_settings)
        rag.chain.invoke.return_value = {
            "answer": "answer",
            "context": [
                Document(page_content="a", metadata={"source": "/p/overview.md"}),
                Document(page_content="b", metadata={"source": "/p/overview.md"}),
            ],
            "question": "anything",
        }
        _, sources = rag.query("anything")
        assert sources.count("overview.md") == 1


# ── Rebuild ───────────────────────────────────────────────────────────────────

class TestRebuildIndex:
    def _mock_vs(self, count: int = 5):
        """Return a fake vectorstore with a fixed doc_count."""
        vs = MagicMock()
        vs._collection.count.return_value = count
        return vs

    def test_rebuild_returns_positive_count(self, sample_docs, tmp_path):
        cfg = Settings(knowledge_dir=sample_docs, chroma_dir=tmp_path / "chroma")
        rag = _make_rag(cfg)
        # Patch _build_vectorstore so we don't fight the live Chroma file lock
        with patch.object(rag, "_build_vectorstore", return_value=self._mock_vs(7)):
            count = rag.rebuild_index()
        assert count > 0

    def test_rebuild_deletes_old_index(self, sample_docs, tmp_path):
        chroma_dir = tmp_path / "chroma"
        cfg = Settings(knowledge_dir=sample_docs, chroma_dir=chroma_dir)
        rag = _make_rag(cfg)
        assert chroma_dir.exists()

        sentinel = chroma_dir / "sentinel.txt"
        sentinel.write_text("old data")

        with patch.object(rag, "_build_vectorstore", return_value=self._mock_vs()):
            rag.rebuild_index()
        # rebuild_index() calls shutil.rmtree before _build_vectorstore
        assert not sentinel.exists()

    def test_rebuild_calls_build_vectorstore(self, sample_docs, tmp_path):
        cfg = Settings(knowledge_dir=sample_docs, chroma_dir=tmp_path / "chroma")
        rag = _make_rag(cfg)
        with patch.object(rag, "_build_vectorstore", return_value=self._mock_vs()) as mock_build:
            rag.rebuild_index()
            mock_build.assert_called_once()


# ── Live DB context ───────────────────────────────────────────────────────────

class TestParseTimeWindow:
    """Unit tests for the time-phrase parser in db_context."""

    def _parse(self, q: str):
        from db_context import parse_time_window
        return parse_time_window(q)

    def test_last_n_days(self):
        assert self._parse("anomalies in the last 7 days") == 7

    def test_past_n_days(self):
        assert self._parse("readings past 14 days") == 14

    def test_last_week(self):
        assert self._parse("What happened last week?") == 7

    def test_past_week(self):
        assert self._parse("any issues past week?") == 7

    def test_this_week(self):
        assert self._parse("results this week") == 7

    def test_last_month(self):
        assert self._parse("Compare sites for the last month") == 30

    def test_past_month(self):
        assert self._parse("average solar past month") == 30

    def test_last_n_weeks(self):
        assert self._parse("last 2 weeks data") == 14

    def test_yesterday(self):
        assert self._parse("what happened yesterday?") == 1

    def test_recent(self):
        assert self._parse("any recent anomalies?") == 7

    def test_recently(self):
        assert self._parse("has it changed recently?") == 7

    def test_no_time_phrase_returns_none(self):
        assert self._parse("What is Helios?") is None

    def test_general_wind_question_returns_none(self):
        assert self._parse("tell me about wind anomaly detection") is None

    def test_case_insensitive(self):
        assert self._parse("Last Week data") == 7


class TestGetLiveContext:
    """Tests for get_live_context() with a minimal in-memory SQLite database."""

    @pytest.fixture
    def helios_db(self, tmp_path):
        """Seed a minimal helios.db with one site and a few observations."""
        import sqlite3
        from datetime import date, timedelta

        db = tmp_path / "helios.db"
        con = sqlite3.connect(str(db))
        con.executescript("""
            CREATE TABLE sites (
                id INTEGER PRIMARY KEY, key TEXT, label TEXT, region TEXT
            );
            CREATE TABLE cleaned_observations (
                id            INTEGER PRIMARY KEY,
                site_id       INTEGER,
                observed_at   TEXT,
                solar_ghi     REAL,
                solar_direct  REAL,
                wind_speed    REAL,
                wind_gusts    REAL,
                wind_direction REAL,
                solar_zscore  REAL,
                wind_zscore   REAL,
                solar_iqr_flag INTEGER DEFAULT 0,
                wind_iqr_flag  INTEGER DEFAULT 0,
                solar_anomaly  INTEGER DEFAULT 0,
                wind_anomaly   INTEGER DEFAULT 0,
                is_daytime     INTEGER DEFAULT 0,
                quality_flag   TEXT    DEFAULT 'ok'
            );
            INSERT INTO sites VALUES (1, 'wellington', 'Wellington', 'New Zealand');
            INSERT INTO sites VALUES (2, 'riyadh',    'Riyadh',     'Saudi Arabia');
        """)
        today     = date.today()
        yesterday = str(today - timedelta(days=1))

        # 2 wind IQR anomalies for Wellington
        # Columns: id, site_id, observed_at, solar_ghi, solar_direct,
        #          wind_speed, wind_gusts, wind_direction, solar_zscore, wind_zscore,
        #          solar_iqr_flag, wind_iqr_flag, solar_anomaly, wind_anomaly, is_daytime, quality_flag
        con.execute(
            "INSERT INTO cleaned_observations VALUES (1,1,?,NULL,NULL,70.0,140.0,NULL,NULL,NULL,0,1,0,1,0,'ok')",
            (yesterday + " 13:00",),
        )
        con.execute(
            "INSERT INTO cleaned_observations VALUES (2,1,?,NULL,NULL,72.0,145.0,NULL,NULL,NULL,0,1,0,1,0,'ok')",
            (yesterday + " 14:00",),
        )
        # Normal daytime solar reading for Riyadh
        con.execute(
            "INSERT INTO cleaned_observations VALUES (3,2,?,900.0,850.0,8.0,20.0,NULL,NULL,NULL,0,0,0,0,1,'ok')",
            (yesterday + " 10:00",),
        )
        con.commit()
        con.close()
        return db

    def test_returns_none_if_db_missing(self, tmp_path):
        from db_context import get_live_context
        result = get_live_context("last 7 days wind anomalies", str(tmp_path / "nope.db"))
        assert result is None

    def test_returns_none_if_no_time_phrase(self, helios_db):
        from db_context import get_live_context
        result = get_live_context("What is Helios?", str(helios_db))
        assert result is None

    def test_returns_string_for_wind_query(self, helios_db):
        from db_context import get_live_context
        result = get_live_context("wind anomalies last 7 days", str(helios_db))
        assert result is not None
        assert isinstance(result, str)
        assert "Wellington" in result

    def test_returns_string_for_solar_query(self, helios_db):
        from db_context import get_live_context
        result = get_live_context("solar radiation past week", str(helios_db))
        assert result is not None
        assert "Riyadh" in result

    def test_returns_string_for_comparison_query(self, helios_db):
        from db_context import get_live_context
        result = get_live_context("compare all sites last month", str(helios_db))
        assert result is not None
        assert "Wellington" in result
        assert "Riyadh" in result

    def test_live_context_includes_date_range(self, helios_db):
        from db_context import get_live_context
        from datetime import date
        result = get_live_context("wind anomalies last 7 days", str(helios_db))
        assert str(date.today()) in result

    def test_anomaly_rows_appear_in_output(self, helios_db):
        from db_context import get_live_context
        result = get_live_context("wind anomalies last 7 days", str(helios_db))
        # The two seeded anomaly rows should be visible
        assert "70.0 km/h" in result or "72.0 km/h" in result

    def test_no_anomalies_returns_none_detected_message(self, tmp_path):
        """When the DB has no anomalies, the function still returns context."""
        import sqlite3
        db = tmp_path / "empty.db"
        con = sqlite3.connect(str(db))
        con.executescript("""
            CREATE TABLE sites (id INTEGER PRIMARY KEY, key TEXT, label TEXT, region TEXT);
            CREATE TABLE cleaned_observations (
                id             INTEGER PRIMARY KEY,
                site_id        INTEGER,
                observed_at    TEXT,
                solar_ghi      REAL,
                solar_direct   REAL,
                wind_speed     REAL,
                wind_gusts     REAL,
                wind_direction REAL,
                solar_zscore   REAL,
                wind_zscore    REAL,
                solar_iqr_flag INTEGER DEFAULT 0,
                wind_iqr_flag  INTEGER DEFAULT 0,
                solar_anomaly  INTEGER DEFAULT 0,
                wind_anomaly   INTEGER DEFAULT 0,
                is_daytime     INTEGER DEFAULT 0,
                quality_flag   TEXT    DEFAULT 'ok'
            );
            INSERT INTO sites VALUES (1, 'riyadh', 'Riyadh', 'Saudi Arabia');
        """)
        con.commit()
        con.close()
        from db_context import get_live_context
        result = get_live_context("wind anomalies last 7 days", str(db))
        assert result is not None
        assert "none detected" in result.lower()


class TestDynamicQueryPath:
    """Tests that rag.query() uses live DB context for time-sensitive questions."""

    def test_time_sensitive_query_uses_live_context(self, test_settings):
        rag = _make_rag(test_settings)
        with patch("rag.get_live_context", return_value="## Live\nWellington: 2 anomalies") as mock_live:
            with patch.object(rag, "_answer_with_context", return_value="Wellington had 2 anomalies."):
                reply, sources = rag.query("wind anomalies last 7 days?")

        mock_live.assert_called_once_with("wind anomalies last 7 days?", str(test_settings.db_path))
        assert reply == "Wellington had 2 anomalies."
        assert "live_database" in sources

    def test_static_query_bypasses_live_context(self, test_settings):
        rag = _make_rag(test_settings)
        with patch("rag.get_live_context", return_value=None) as mock_live:
            rag.query("What anomaly method does Helios use?")

        mock_live.assert_called_once()
        rag.chain.invoke.assert_called_once_with("What anomaly method does Helios use?")

    def test_live_database_appears_first_in_sources(self, test_settings):
        rag = _make_rag(test_settings)
        with patch("rag.get_live_context", return_value="## Live data"):
            with patch.object(rag, "_answer_with_context", return_value="Answer."):
                _, sources = rag.query("anomalies last week?")
        assert sources[0] == "live_database"

    def test_chain_not_called_on_dynamic_path(self, test_settings):
        rag = _make_rag(test_settings)
        with patch("rag.get_live_context", return_value="## Live data"):
            with patch.object(rag, "_answer_with_context", return_value="Answer."):
                rag.query("anomalies last 7 days?")
        rag.chain.invoke.assert_not_called()

    def test_answer_with_context_called_on_dynamic_path(self, test_settings):
        rag = _make_rag(test_settings)
        with patch("rag.get_live_context", return_value="## Live data"):
            with patch.object(rag, "_answer_with_context", return_value="Answer.") as mock_ans:
                rag.query("wind anomalies last 7 days?")
        mock_ans.assert_called_once()
        context_arg, question_arg = mock_ans.call_args[0]
        assert "## Live data" in context_arg
        assert question_arg == "wind anomalies last 7 days?"


# ── Config ────────────────────────────────────────────────────────────────────

class TestSettings:
    def test_default_model(self):
        cfg = Settings()
        assert cfg.llm_model == "llama3.2"

    def test_default_embedding_model(self):
        cfg = Settings()
        assert cfg.embedding_model == "all-MiniLM-L6-v2"

    def test_default_top_k(self):
        cfg = Settings()
        assert cfg.top_k == 4

    def test_default_port(self):
        cfg = Settings()
        assert cfg.api_port == 8000

    def test_custom_values_accepted(self, tmp_path):
        cfg = Settings(
            llm_model="mistral",
            top_k=6,
            temperature=0.5,
            chroma_dir=tmp_path / "c",
            knowledge_dir=tmp_path / "k",
        )
        assert cfg.llm_model == "mistral"
        assert cfg.top_k == 6
        assert cfg.temperature == 0.5

    def test_temperature_bounds(self):
        with pytest.raises(Exception):
            Settings(temperature=3.0)  # above max of 2.0
