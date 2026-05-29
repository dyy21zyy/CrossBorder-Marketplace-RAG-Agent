"""Embedding model loader."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from sentence_transformers import SentenceTransformer

from src.config import get_settings


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _resolve_model_path(model_name: str) -> str:
    """Prefer an existing local model path over a remote Hugging Face id."""
    root = _project_root()
    candidate = Path(model_name).expanduser()
    if candidate.exists():
        return str(candidate)

    repo_relative_candidate = root / model_name
    if repo_relative_candidate.exists():
        return str(repo_relative_candidate)

    local_name = model_name.rstrip("/").split("/")[-1]
    local_candidate = root / "models" / local_name
    if local_candidate.exists():
        return str(local_candidate)

    return model_name


@lru_cache(maxsize=None)
def _load_embedding_model_cached(resolved_model: str) -> SentenceTransformer:
    try:
        return SentenceTransformer(resolved_model)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(
            "Failed to load embedding model. "
            "Check that models/bge-small-en-v1.5 exists, or set HF_ENDPOINT "
            "to a reachable Hugging Face mirror, or update embedding_model_name "
            "in configs/default.yaml. "
            f"Resolved model: {resolved_model}. Error: {exc}"
        ) from exc


def load_embedding_model(model_name: str | None = None) -> SentenceTransformer:
    """Load and cache the configured sentence-transformers embedding model."""
    settings = get_settings()
    configured_model = model_name or settings.embedding_model_name
    resolved_model = _resolve_model_path(configured_model)
    return _load_embedding_model_cached(resolved_model)
