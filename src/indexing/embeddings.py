"""Embedding model loader."""

from __future__ import annotations

from sentence_transformers import SentenceTransformer

from src.config import get_settings


def load_embedding_model(model_name: str | None = None) -> SentenceTransformer:
    """Load sentence-transformers model from config or explicit argument."""
    settings = get_settings()
    resolved_model = model_name or settings.embedding_model_name
    try:
        return SentenceTransformer(resolved_model)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Failed to load embedding model from Hugging Face. "
            "You may set HF_ENDPOINT=https://hf-mirror.com and retry. "
            f"Model: {resolved_model}. Error: {exc}"
        ) from exc
