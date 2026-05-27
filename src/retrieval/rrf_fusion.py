"""Reciprocal Rank Fusion (RRF) utilities."""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _extract_result_id(item: dict[str, Any]) -> str | None:
    """Read canonical id from a retrieval result."""
    for key in ("id", "chunk_id", "evidence_id"):
        value = item.get(key)
        if value:
            return str(value)
    return None


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int = 60,
) -> list[dict[str, Any]]:
    """Fuse multiple ranked lists using Reciprocal Rank Fusion.

    Each list is assumed to be sorted by descending relevance.
    """
    scores: dict[str, float] = {}
    id_to_item: dict[str, dict[str, Any]] = {}

    for ranked_list in result_lists:
        for rank, item in enumerate(ranked_list, start=1):
            result_id = _extract_result_id(item)
            if result_id is None:
                continue
            scores[result_id] = scores.get(result_id, 0.0) + 1.0 / (k + rank)
            if result_id not in id_to_item:
                id_to_item[result_id] = deepcopy(item)

    fused = []
    for result_id, score in scores.items():
        enriched = deepcopy(id_to_item[result_id])
        enriched["rrf_score"] = score
        fused.append(enriched)

    fused.sort(key=lambda x: x["rrf_score"], reverse=True)
    return fused
