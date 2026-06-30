"""
ingest.py — CLI script to build or rebuild the ChromaDB vector index.

Run this once before starting the chatbot server, or any time you update
the knowledge documents in chatbot/knowledge/.

Usage:
    python ingest.py                   # build index using default settings
    python ingest.py --force           # delete existing index and rebuild
    python ingest.py --knowledge ./knowledge --chroma ./chroma_db
"""

import argparse
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger("helios.ingest")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build the Helios chatbot ChromaDB index from markdown knowledge documents."
    )
    parser.add_argument(
        "--knowledge",
        type=Path,
        default=None,
        help="Path to the knowledge/ directory (default: chatbot/knowledge/)",
    )
    parser.add_argument(
        "--chroma",
        type=Path,
        default=None,
        help="Path to persist ChromaDB (default: chatbot/chroma_db/)",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Embedding model name (default: all-MiniLM-L6-v2)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Delete existing index and rebuild from scratch.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Build settings — override only the values the user supplied
    from config import Settings
    overrides: dict = {}
    if args.knowledge:
        overrides["knowledge_dir"] = args.knowledge
    if args.chroma:
        overrides["chroma_dir"] = args.chroma
    if args.model:
        overrides["embedding_model"] = args.model

    cfg = Settings(**overrides)

    log.info("Knowledge dir : %s", cfg.knowledge_dir)
    log.info("ChromaDB dir  : %s", cfg.chroma_dir)
    log.info("Embedding model: %s", cfg.embedding_model)

    # Validate knowledge dir
    if not cfg.knowledge_dir.exists():
        log.error("Knowledge directory does not exist: %s", cfg.knowledge_dir)
        sys.exit(1)

    md_files = list(cfg.knowledge_dir.glob("**/*.md"))
    if not md_files:
        log.error("No .md files found in %s", cfg.knowledge_dir)
        sys.exit(1)

    log.info("Found %d knowledge file(s):", len(md_files))
    for f in sorted(md_files):
        log.info("  %s", f.name)

    # Import RAG after settings are ready
    from rag import HeliosRAG
    rag = HeliosRAG(cfg=cfg)

    if args.force:
        log.info("--force: deleting existing index and rebuilding…")
        count = rag.rebuild_index()
    else:
        count = rag.doc_count
        if count == 0:
            log.info("No existing index — building…")
            count = rag.rebuild_index()
        else:
            log.info("Index already exists with %d chunks. Use --force to rebuild.", count)

    log.info("Done. %d chunks in the vector store.", count)

    # Quick smoke test
    log.info("Running smoke test query…")
    reply, sources = rag.query("What is Helios?")
    if reply:
        log.info("Smoke test passed. Reply snippet: %s…", reply[:120])
    else:
        log.warning("Smoke test returned an empty reply — check your Ollama setup.")


if __name__ == "__main__":
    main()
