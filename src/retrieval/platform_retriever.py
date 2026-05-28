"""Retriever for Temu IP policy using hybrid RAG."""

from __future__ import annotations

from src.config import get_settings
from src.indexing.bm25_index import bm25_search, load_bm25_index
from src.indexing.chroma_store import load_chroma_collection, vector_search
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.rrf_fusion import reciprocal_rank_fusion
from src.schemas import EvidenceItem


class PlatformPolicyRetriever:
    def __init__(self, top_k: int | None = None) -> None:
        settings = get_settings()
        self.top_k = top_k or settings.top_k
        self.rerank_input_top_k = settings.rerank_input_top_k
        self.rerank_top_k = settings.rerank_top_k
        self.collection = load_chroma_collection(settings.chroma_platform_dir, "temu_ip_policy")
        self.bm25_index = load_bm25_index(settings.bm25_platform_path)
        self.reranker = CrossEncoderReranker()

    def vector_search(self, query: str, top_k: int | None = None) -> list[dict]:
        return vector_search(self.collection, query, top_k=top_k or self.top_k)

    def bm25_search(self, query: str, top_k: int | None = None) -> list[dict]:
        return bm25_search(self.bm25_index, query, top_k=top_k or self.top_k)

    def hybrid_search(self, query: str, top_k: int = 5, use_reranker: bool = False) -> list[EvidenceItem]:
        input_k = self.rerank_input_top_k
        vector_results = self.vector_search(query, top_k=input_k)
        bm25_results = self.bm25_search(query, top_k=input_k)
        fused = reciprocal_rank_fusion([vector_results, bm25_results])
        for i, item in enumerate(fused, start=1):
            item.setdefault("original_score", float(item.get("rrf_score", item.get("score", 0.0))))
            item.setdefault("original_rank", i)
            item["retrieval_method"] = "rrf"

        if use_reranker:
            reranked = self.reranker.rerank(query, fused, top_k=self.rerank_top_k)
            selected = reranked
        else:
            selected = fused[:top_k]

        evidence: list[EvidenceItem] = []
        for rank, item in enumerate(selected, start=1):
            meta = item.get("metadata", {})
            evidence.append(EvidenceItem(evidence_id=str(item.get("chunk_id", item.get("id", ""))), evidence_type="platform_policy", source=str(item.get("source", "Temu IP Policy")), title=f"Temu IP Policy - {item.get('section', 'general')}", snippet=str(item.get("text", "")), score=float(item.get("reranker_score", item.get("rrf_score", item.get("score", 0.0)))), metadata={**meta, "section": item.get("section"), "page_start": item.get("page_start"), "page_end": item.get("page_end"), "retrieval_method": item.get("retrieval_method", "rrf"), "rrf_score": item.get("rrf_score", 0.0), "reranker_score": item.get("reranker_score"), "rank": rank}))
        return evidence
