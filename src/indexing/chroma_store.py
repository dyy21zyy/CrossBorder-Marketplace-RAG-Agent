"""Chroma vector store helpers."""

from __future__ import annotations

import logging
import math
from collections.abc import Mapping
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


def _is_missing_value(value: Any) -> bool:
    """Return True for null-like scalar values that Chroma cannot store."""
    if value is None:
        return True
    if isinstance(value, float):
        return math.isnan(value)

    # pandas/numpy null sentinels such as pd.NA, pd.NaT, and numpy.nan should
    # be treated as empty metadata values without requiring pandas as a runtime
    # dependency for this module.
    type_name = type(value).__name__
    if type_name in {"NAType", "NaTType"}:
        return True

    try:
        return bool(value != value)
    except Exception:  # noqa: BLE001
        return False


def _sanitize_scalar(value: Any) -> str | int | float | bool:
    """Convert one metadata value to a Chroma-safe scalar."""
    if _is_missing_value(value):
        return ""
    if isinstance(value, str | int | float | bool):
        return value
    return str(value)


def _sanitize_list(values: list[Any]) -> list[str | int | float | bool] | str:
    """Convert list metadata while preserving non-empty list shape.

    Chroma requires non-empty list metadata to contain only scalar values of one
    type, so mixed sanitized lists are stringified element-by-element.
    """
    if not values:
        return ""

    sanitized: list[str | int | float | bool] = []
    for item in values:
        if isinstance(item, str | int | float | bool) or _is_missing_value(item):
            sanitized.append(_sanitize_scalar(item))
        else:
            sanitized.append(str(item))

    value_types = {type(item) for item in sanitized}
    if len(value_types) > 1:
        return [str(item) for item in sanitized]
    return sanitized


def sanitize_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    """Flatten and normalize metadata into values accepted by Chroma.

    Chroma metadata cannot contain nested dictionaries or null-like scalar
    values. This function recursively flattens dictionaries with underscore
    separators, converts all keys to strings, converts empty lists to empty
    strings, preserves non-empty lists with Chroma-safe scalar members, and
    stringifies unsupported complex objects.
    """

    sanitized: dict[str, Any] = {}

    def flatten(prefix: str, value: Any) -> None:
        if isinstance(value, Mapping):
            if not value:
                sanitized[prefix] = ""
                return
            for nested_key, nested_value in value.items():
                key = str(nested_key)
                flattened_key = f"{prefix}_{key}" if prefix else key
                flatten(flattened_key, nested_value)
            return

        if isinstance(value, list):
            sanitized[prefix] = _sanitize_list(value)
            return

        sanitized[prefix] = _sanitize_scalar(value)

    for key, value in (metadata or {}).items():
        flatten(str(key), value)

    return sanitized


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
        metadatas = [sanitize_metadata({k: v for k, v in d.items() if k != "text"}) for d in batch]
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
