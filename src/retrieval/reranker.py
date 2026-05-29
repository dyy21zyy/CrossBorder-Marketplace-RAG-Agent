from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path
from typing import Any

from sentence_transformers import CrossEncoder

from src.config import get_settings

logger = logging.getLogger(__name__)

LOCAL_RERANKER_MODEL_PATH = Path("models/bge-reranker-base")


def _resolve_model_name(model_name: str | None) -> str:
    """Prefer the checked-in local reranker when present, otherwise use config/HF name."""
    if model_name:
        return model_name
    if LOCAL_RERANKER_MODEL_PATH.exists():
        return str(LOCAL_RERANKER_MODEL_PATH)
    return get_settings().reranker_model_name


@lru_cache(maxsize=2)
def _load_cross_encoder(model_name: str):
    """Load and cache CrossEncoder weights once per model path/name."""
    return CrossEncoder(model_name)


class CrossEncoderReranker:
    """Cross-encoder reranker with cached model loading and explicit fallback warnings."""

    def __init__(self, model_name: str | None = None, use_reranker: bool | None = None) -> None:
        settings = get_settings()
        self.model_name = _resolve_model_name(model_name)
        self.use_reranker = settings.use_reranker if use_reranker is None else use_reranker
        self.rerank_input_top_k = settings.rerank_input_top_k
        self.rerank_top_k = settings.rerank_top_k
        self._model = None
        self._available = False
        self._load_attempted = False
        self.load_error = ""

        if self.use_reranker:
            self._init_model()

    def _warn(self, message: str) -> None:
        self.load_error = message
        logger.warning(message)

    def _init_model(self) -> None:
        if self._load_attempted:
            return
        self._load_attempted = True
        try:
            self._model = _load_cross_encoder(self.model_name)
            self._available = True
        except Exception as e:  # noqa: BLE001
            self._model = None
            self._available = False
            self._warn(
                f"Failed to load reranker model '{self.model_name}': {e}. "
                "Falling back to RRF/vector/BM25 order. Set HF_ENDPOINT=https://hf-mirror.com, "
                "place the model under models/bge-reranker-base, or disable use_reranker."
            )

    @staticmethod
    def _get_text(candidate: dict[str, Any]) -> str:
        return str(candidate.get("reranker_text") or candidate.get("text") or candidate.get("page_content") or candidate.get("snippet") or "")

    def _fallback(self, candidates: list[dict[str, Any]], top_k: int | None) -> list[dict[str, Any]]:
        limit = top_k or self.rerank_top_k
        return [dict(row) for row in candidates[:limit]]

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int | None = None) -> list[dict[str, Any]]:
        if not candidates:
            return []
        if not self.use_reranker:
            return self._fallback(candidates, top_k)
        if self._model is None and not self._available:
            self._init_model()
        if not self._available or self._model is None:
            if not self.load_error:
                self._warn("Reranker requested but no CrossEncoder model is available; falling back to input order.")
            return self._fallback(candidates, top_k)

        try:
            pairs = [(query, self._get_text(c)) for c in candidates]
            scores = self._model.predict(pairs)
        except Exception as e:  # noqa: BLE001
            self._available = False
            self._warn(f"Reranker prediction failed for model '{self.model_name}': {e}. Falling back to input order.")
            return self._fallback(candidates, top_k)

        out: list[dict[str, Any]] = []
        for idx, (c, s) in enumerate(zip(candidates, scores, strict=False), start=1):
            row = dict(c)
            row.setdefault("original_score", float(c.get("rrf_score", c.get("score", 0.0))))
            row.setdefault("original_rank", idx)
            row["reranker_score"] = float(s)
            out.append(row)

        out.sort(key=lambda x: x.get("reranker_score", 0.0), reverse=True)
        for i, row in enumerate(out, start=1):
            row["reranker_rank"] = i
            row["retrieval_method"] = "reranker"

        return out[: (top_k or self.rerank_top_k)]
