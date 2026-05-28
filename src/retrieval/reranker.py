from __future__ import annotations

from typing import Any

from src.config import get_settings


class CrossEncoderReranker:
    """Cross-encoder reranker with graceful fallback."""

    def __init__(self, model_name: str | None = None, use_reranker: bool | None = None) -> None:
        settings = get_settings()
        self.model_name = model_name or settings.reranker_model_name
        self.use_reranker = settings.use_reranker if use_reranker is None else use_reranker
        self.rerank_input_top_k = settings.rerank_input_top_k
        self.rerank_top_k = settings.rerank_top_k
        self._model = None
        self._available = False
        self.load_error = ""

        if self.use_reranker:
            self._init_model()

    def _init_model(self) -> None:
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            self._available = True
        except Exception as e:  # noqa: BLE001
            self.load_error = (
                f"Failed to load reranker model '{self.model_name}': {e}. "
                "Set HF_ENDPOINT=https://hf-mirror.com or disable use_reranker."
            )
            self._available = False

    @staticmethod
    def _get_text(candidate: dict[str, Any]) -> str:
        return str(candidate.get("text") or candidate.get("page_content") or candidate.get("snippet") or "")

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int | None = None) -> list[dict[str, Any]]:
        if not candidates:
            return []
        if not self.use_reranker or not self._available or self._model is None:
            return candidates[: (top_k or self.rerank_top_k)]

        pairs = [(query, self._get_text(c)) for c in candidates]
        scores = self._model.predict(pairs)

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
