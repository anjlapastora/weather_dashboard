"""
rag.py — LangChain LCEL RAG pipeline for the Helios chatbot.

Pipeline:
  1. Load markdown documents from knowledge/
  2. Split into overlapping chunks (langchain-text-splitters)
  3. Embed with sentence-transformers (langchain-huggingface)
  4. Store / load from ChromaDB (langchain-chroma)
  5. On query: retrieve top-k chunks → format context → prompt Ollama → parse reply
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.document_loaders import DirectoryLoader, TextLoader
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_ollama import OllamaLLM
from langchain_text_splitters import RecursiveCharacterTextSplitter

from config import Settings, settings as default_settings

log = logging.getLogger(__name__)

# ── System prompt ─────────────────────────────────────────────────────────────

_PROMPT_TEMPLATE = """\
You are the Helios Assistant, an expert on the Helios Solar & Wind Monitoring Dashboard.
Answer the question using ONLY the context provided below.
Be concise and accurate. If the answer is not in the context, say so clearly.
Do not make up information.

Context:
{context}

Question: {question}

Answer:"""


def _format_docs(docs: list[Document]) -> str:
    return "\n\n".join(d.page_content for d in docs)


# ── RAG pipeline class ────────────────────────────────────────────────────────

class HeliosRAG:
    """
    Retrieval-Augmented Generation pipeline for the Helios chatbot.

    Usage:
        rag = HeliosRAG()
        reply, sources = rag.query("What anomaly method does Helios use?")
    """

    def __init__(self, cfg: Settings = default_settings) -> None:
        self.cfg = cfg
        log.info("Initialising embeddings model: %s", cfg.embedding_model)
        self.embeddings = HuggingFaceEmbeddings(
            model_name=cfg.embedding_model,
            model_kwargs={"device": "cpu"},
            encode_kwargs={"normalize_embeddings": True},
        )
        log.info("Initialising Ollama LLM: %s @ %s", cfg.llm_model, cfg.ollama_base_url)
        self.llm = OllamaLLM(
            model=cfg.llm_model,
            base_url=cfg.ollama_base_url,
            temperature=cfg.temperature,
        )
        self.vectorstore = self._init_vectorstore()
        self.chain = self._build_chain()

    # ── Public API ────────────────────────────────────────────────────────────

    def query(self, question: str) -> tuple[str, list[str]]:
        """
        Run a RAG query.

        Returns:
            (reply, sources) where sources is a sorted list of unique knowledge
            file names that contributed to the answer.
        """
        result = self.chain.invoke(question)
        reply = result.get("answer", "").strip()
        source_docs: list[Document] = result.get("context", [])
        sources = sorted({
            Path(doc.metadata.get("source", "")).name
            for doc in source_docs
            if doc.metadata.get("source")
        })
        return reply, sources

    def rebuild_index(self) -> int:
        """
        Delete and rebuild the ChromaDB index from the knowledge directory.

        Returns:
            Number of chunks indexed.
        """
        chroma_path = Path(self.cfg.chroma_dir)
        if chroma_path.exists():
            shutil.rmtree(chroma_path)
            log.info("Deleted existing ChromaDB at %s", chroma_path)

        self.vectorstore = self._build_vectorstore()
        self.chain = self._build_chain()
        count = self.doc_count
        log.info("Index rebuilt: %d chunks", count)
        return count

    @property
    def doc_count(self) -> int:
        """Number of chunks currently in the vector store."""
        try:
            return self.vectorstore._collection.count()
        except Exception:
            return 0

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _init_vectorstore(self) -> Chroma:
        chroma_path = Path(self.cfg.chroma_dir)
        if chroma_path.exists() and any(chroma_path.iterdir()):
            log.info("Loading existing ChromaDB from %s", chroma_path)
            return Chroma(
                persist_directory=str(chroma_path),
                embedding_function=self.embeddings,
                collection_name=self.cfg.collection_name,
            )
        log.info("No existing index found — building from scratch")
        return self._build_vectorstore()

    def _build_vectorstore(self) -> Chroma:
        docs = self._load_docs()
        if not docs:
            raise ValueError(
                f"No markdown documents found in {self.cfg.knowledge_dir}. "
                "Add .md files to chatbot/knowledge/ and retry."
            )

        splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.cfg.chunk_size,
            chunk_overlap=self.cfg.chunk_overlap,
            separators=["\n## ", "\n### ", "\n\n", "\n", " "],
        )
        chunks = splitter.split_documents(docs)
        log.info(
            "Loaded %d documents → %d chunks (chunk_size=%d, overlap=%d)",
            len(docs), len(chunks), self.cfg.chunk_size, self.cfg.chunk_overlap,
        )

        return Chroma.from_documents(
            documents=chunks,
            embedding=self.embeddings,
            persist_directory=str(self.cfg.chroma_dir),
            collection_name=self.cfg.collection_name,
        )

    def _load_docs(self) -> list[Document]:
        knowledge_dir = Path(self.cfg.knowledge_dir)
        if not knowledge_dir.exists():
            raise FileNotFoundError(f"Knowledge directory not found: {knowledge_dir}")

        loader = DirectoryLoader(
            str(knowledge_dir),
            glob="**/*.md",
            loader_cls=TextLoader,
            loader_kwargs={"encoding": "utf-8"},
            show_progress=False,
        )
        docs = loader.load()
        log.info("Loaded %d documents from %s", len(docs), knowledge_dir)
        return docs

    def _build_chain(self):
        """Build the LCEL RAG chain that returns {answer, context, question}."""
        prompt = PromptTemplate(
            input_variables=["context", "question"],
            template=_PROMPT_TEMPLATE,
        )
        retriever = self.vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.cfg.top_k},
        )

        # Inner chain: takes {context: [docs], question: str} → answer str
        answer_chain = (
            RunnablePassthrough.assign(context=lambda x: _format_docs(x["context"]))
            | prompt
            | self.llm
            | StrOutputParser()
        )

        # Outer chain: retrieves docs then generates answer, keeping context for sources
        return RunnableParallel(
            {"context": retriever, "question": RunnablePassthrough()}
        ).assign(answer=answer_chain)
