"""Chroma vector store helpers."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import chromadb

from src.indexing.embeddings import load_embedding_model

logger = logging.getLogger(__name__)


class _CollectionWrapper:
    def __init__(self, collection: Any) -> None:
        self.collection = collection


def _batch_iter(seq: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    for i in range(0, len(seq), batch_size):
        yield seq[i:i + batch_size]


def build_chroma_index(documents: list[dict[str, Any]], persist_dir: str, collection_name: str, *, batch_size: int = 1024, reset: bool = True) -> _CollectionWrapper:
    logger.info("Building Chroma index: docs=%d, batch_size=%d, reset=%s", len(documents), batch_size, reset)
    Path(persist_dir).mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=persist_dir)
    if reset:
        try:
            client.delete_collection(collection_name)
        except Exception:  # noqa: BLE001
            pass
    collection = client.get_or_create_collection(name=collection_name)

    model = load_embedding_model()
    for base_idx, batch in enumerate(_batch_iter(documents, max(1, batch_size))):
        texts = [d.get("text", "") for d in batch]
        embeddings = model.encode(texts, normalize_embeddings=True).tolist()
        ids = [str(d.get("chunk_id", f"chunk_{base_idx}_{i}")) for i, d in enumerate(batch)]
        metadatas = [{k: v for k, v in d.items() if k != "text"} for d in batch]
        collection.add(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        logger.info("Chroma batch added: %d documents", len(batch))
    return _CollectionWrapper(collection)


def load_chroma_collection(persist_dir: str, collection_name: str) -> _CollectionWrapper:
    client = chromadb.PersistentClient(path=persist_dir)
    collection = client.get_collection(name=collection_name)
    return _CollectionWrapper(collection)


def vector_search(collection: _CollectionWrapper, query: str, top_k: int = 5) -> list[dict[str, Any]]:
    model = load_embedding_model()
    query_emb = model.encode([query], normalize_embeddings=True).tolist()
    result = collection.collection.query(query_embeddings=query_emb, n_results=top_k)

    ids = result.get("ids", [[]])[0]
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]

    outputs: list[dict[str, Any]] = []
    for idx, chunk_id in enumerate(ids):
        meta = metas[idx] or {}
        distance = float(distances[idx]) if idx < len(distances) else 0.0
        outputs.append(
            {
                "id": chunk_id,
                "chunk_id": chunk_id,
                "text": docs[idx] if idx < len(docs) else "",
                "score": 1.0 / (1.0 + distance),
                "source": meta.get("source", "Temu IP Policy"),
                "section": meta.get("section", "general"),
                "page_start": meta.get("page_start"),
                "page_end": meta.get("page_end"),
                "metadata": meta,
            }
        )
    return outputs
