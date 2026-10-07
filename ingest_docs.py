"""
ingest_docs.py
──────────────
One-time script to ingest crop-guide text files into ChromaDB.
Run this before starting the server:
    python -m scripts.ingest_docs

Embedding strategy (automatic fallback):
  1. sentence-transformers  — best quality (requires sklearn DLL on Windows)
  2. ChromaDB default embedding — works everywhere, no extra DLL needed
"""

import sys
from pathlib import Path

# Make sure the project root is on sys.path when run as a module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import chromadb
from chromadb.config import Settings as ChromaSettings
from loguru import logger

from backend.config import get_settings

settings = get_settings()

# ── Config ────────────────────────────────────────────────────────────────────

CHUNK_SIZE = 500      # characters per chunk
CHUNK_OVERLAP = 80    # overlap between consecutive chunks
DATA_DIR = Path("backend/data/crop_guides")

# ── Try to load sentence-transformers; fall back to ChromaDB built-in ─────────

_USE_SENTENCE_TRANSFORMERS = False
_embedder = None

try:
    from sentence_transformers import SentenceTransformer
    _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    _USE_SENTENCE_TRANSFORMERS = True
    logger.info("Using sentence-transformers for embeddings (best quality)")
except Exception as exc:
    logger.warning(
        f"sentence-transformers unavailable ({exc}). "
        "Using ChromaDB default embedding (onnxruntime — no sklearn needed)."
    )

# ChromaDB default embedding function (onnxruntime-based, no sklearn DLL)
try:
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    _chroma_ef = DefaultEmbeddingFunction()
except Exception:
    _chroma_ef = None


def _embed(chunks: list[str]) -> list[list[float]] | None:
    """Return embeddings or None to let ChromaDB handle embedding itself."""
    if _USE_SENTENCE_TRANSFORMERS and _embedder is not None:
        return _embedder.encode(chunks, show_progress_bar=False).tolist()
    return None   # ChromaDB will call its own EF at query time


def chunk_text(text: str, size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP):
    """Split text into overlapping character chunks."""
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        start += size - overlap
    return chunks


def ingest_documents():
    logger.info(f"Connecting to ChromaDB at: {settings.chroma_persist_dir}")

    # Use ChromaDB's default EF if sentence-transformers is unavailable
    ef_kwargs = {}
    if not _USE_SENTENCE_TRANSFORMERS and _chroma_ef is not None:
        ef_kwargs["embedding_function"] = _chroma_ef

    client = chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )

    # Reset collection for fresh ingest
    try:
        client.delete_collection(settings.chroma_collection)
        logger.info("Deleted existing collection for fresh ingest")
    except Exception:
        pass

    collection = client.create_collection(
        name=settings.chroma_collection,
        metadata={"hnsw:space": "cosine"},
        **ef_kwargs,
    )

    text_files = sorted(DATA_DIR.glob("*.txt"))
    if not text_files:
        logger.error(f"No .txt files found in {DATA_DIR}")
        return

    total_chunks = 0
    for fpath in text_files:
        logger.info(f"Ingesting: {fpath.name}")
        text = fpath.read_text(encoding="utf-8")
        chunks = chunk_text(text)

        ids = [f"{fpath.stem}_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": fpath.name, "chunk_index": i} for i in range(len(chunks))]

        embeddings = _embed(chunks)
        if embeddings is not None:
            collection.add(documents=chunks, embeddings=embeddings, ids=ids, metadatas=metadatas)
        else:
            # Let ChromaDB compute embeddings via its own EF
            collection.add(documents=chunks, ids=ids, metadatas=metadatas)

        total_chunks += len(chunks)
        logger.info(f"  → {len(chunks)} chunks ingested from {fpath.name}")

    logger.success(
        f"Ingestion complete. Total chunks: {total_chunks} in "
        f"collection '{settings.chroma_collection}'"
    )


if __name__ == "__main__":
    ingest_documents()
