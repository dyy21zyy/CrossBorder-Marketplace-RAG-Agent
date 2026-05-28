"""Retriever for Temu IP policy using hybrid RAG."""

from __future__ import annotations

from src.config import get_settings
from src.indexing.bm25_index import bm25_search, load_bm25_index
from src.indexing.chroma_store import load_chroma_collection, vector_search
from src.retrieval.rrf_fusion import reciprocal_rank_fusion
from src.schemas import EvidenceItem


class PlatformPolicyRetriever:
    def __init__(self, top_k: int | None = None) -> None:
        settings = get_settings()
        self.top_k = top_k or settings.top_k
        self.collection = load_chroma_collection(settings.chroma_platform_dir, "temu_ip_policy")
        self.bm25_index = load_bm25_index(settings.bm25_platform_path)

    def vector_search(self, query: str) -> list[dict]:
        return vector_search(self.collection, query, top_k=self.top_k)

    def bm25_search(self, query: str) -> list[dict]:
        return bm25_search(self.bm25_index, query, top_k=self.top_k)

    def hybrid_search(self, query: str) -> list[EvidenceItem]:
        vector_results = self.vector_search(query)
        bm25_results = self.bm25_search(query)
        fused = reciprocal_rank_fusion([vector_results, bm25_results])[: self.top_k]
        evidence: list[EvidenceItem] = []
        for item in fused:
            meta = item.get("metadata", {})
            evidence.append(
                EvidenceItem(
                    evidence_id=str(item.get("chunk_id", item.get("id", ""))),
                    evidence_type="platform_policy",
                    source=str(item.get("source", "Temu IP Policy")),
                    title=f"Temu IP Policy - {item.get('section', 'general')}",
                    snippet=str(item.get("text", "")),
                    score=float(item.get("rrf_score", item.get("score", 0.0))),
                    metadata={
                        **meta,
                        "section": item.get("section"),
                        "page_start": item.get("page_start"),
                        "page_end": item.get("page_end"),
                    },
                )
            )
        return evidence
