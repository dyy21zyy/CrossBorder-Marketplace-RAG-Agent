"""BM25 index helpers for platform policy chunks."""

from __future__ import annotations

import pickle
from pathlib import Path
from typing import Any

from rank_bm25 import BM25Okapi


def _tokenize(text: str) -> list[str]:
    return text.lower().split()


def build_bm25_index(documents: list[dict[str, Any]], output_path: str) -> None:
    corpus_tokens = [_tokenize(d.get("text", "")) for d in documents]
    bm25 = BM25Okapi(corpus_tokens)
    payload = {"bm25": bm25, "documents": documents}
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as f:
        pickle.dump(payload, f)


def load_bm25_index(path: str) -> dict[str, Any]:
    with Path(path).open("rb") as f:
        return pickle.load(f)


def bm25_search(index_data: dict[str, Any], query: str, top_k: int = 5) -> list[dict[str, Any]]:
    bm25: BM25Okapi = index_data["bm25"]
    documents: list[dict[str, Any]] = index_data["documents"]
    scores = bm25.get_scores(_tokenize(query))
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)[:top_k]
    results: list[dict[str, Any]] = []
    for rank, (doc_idx, score) in enumerate(ranked, start=1):
        d = documents[doc_idx]
        results.append(
            {
                "id": d.get("chunk_id", f"bm25_{rank}"),
                "chunk_id": d.get("chunk_id", f"bm25_{rank}"),
                "text": d.get("text", ""),
                "score": float(score),
                "source": d.get("source", "Temu IP Policy"),
                "section": d.get("section", "general"),
                "page_start": d.get("page_start"),
                "page_end": d.get("page_end"),
                "metadata": d.get("metadata", {}),
            }
        )
    return results
