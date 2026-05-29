"""Claim-level hybrid retriever using Chroma + BM25 + RRF."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.config import get_settings
from src.indexing.bm25_index import bm25_search as bm25_lookup
from src.indexing.bm25_index import build_bm25_index, load_bm25_index
from src.indexing.chroma_store import build_chroma_index, load_chroma_collection, vector_search
from src.preprocessing.claim_group_builder import ClaimGroup
from src.retrieval.reranker import CrossEncoderReranker
from src.retrieval.rrf_fusion import reciprocal_rank_fusion


class ClaimRetriever:
    def __init__(self, chroma_dir: str = "indexes/chroma", bm25_path: str = "indexes/bm25/claim_groups.pkl", collection_name: str = "claim_groups") -> None:
        settings = get_settings()
        self.chroma_dir = settings.chroma_claims_dir
        self.bm25_path = settings.bm25_claims_path
        self.collection_name = collection_name
        self.rerank_input_top_k = settings.rerank_input_top_k
        self.rerank_top_k = settings.rerank_top_k
        self.collection = None
        self.bm25_data: dict[str, Any] | None = None
        self.reranker: CrossEncoderReranker | None = None

    def build_claim_documents(self, claim_groups: list[ClaimGroup]) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for idx, cg in enumerate(claim_groups):
            docs.append({"chunk_id": f"{cg.patent_id}_{cg.independent_claim_number}_{idx}", "text": cg.claim_group_text, "source": cg.source, "section": "patent_claim_group", "metadata": asdict(cg), "patent_id": cg.patent_id, "independent_claim_number": cg.independent_claim_number})
        return docs

    def build_indexes(self, claim_groups: list[ClaimGroup], *, batch_size: int = 1024, force_rebuild: bool = False) -> None:
        docs = self.build_claim_documents(claim_groups)
        self.collection = build_chroma_index(docs, persist_dir=self.chroma_dir, collection_name=self.collection_name, batch_size=batch_size, reset=force_rebuild)
        Path(self.bm25_path).parent.mkdir(parents=True, exist_ok=True)
        build_bm25_index(docs, self.bm25_path)
        self.bm25_data = load_bm25_index(self.bm25_path)

    def _ensure_loaded(self) -> None:
        if self.collection is None:
            self.collection = load_chroma_collection(self.chroma_dir, self.collection_name)
        if self.bm25_data is None:
            self.bm25_data = load_bm25_index(self.bm25_path)

    def vector_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        self._ensure_loaded()
        return vector_search(self.collection, query, top_k=top_k)

    def bm25_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        self._ensure_loaded()
        return bm25_lookup(self.bm25_data or {}, query, top_k=top_k)

    @staticmethod
    def _claim_reranker_text(row: dict[str, Any]) -> str:
        metadata = row.get("metadata", {}) or {}
        return (
            f"patent_id: {metadata.get('patent_id', row.get('patent_id', ''))}; "
            f"independent_claim_number: {metadata.get('independent_claim_number', row.get('independent_claim_number', ''))}; "
            f"dependent_claim_numbers: {metadata.get('dependent_claim_numbers', row.get('dependent_claim_numbers', []))}; "
            f"claim_group_text: {metadata.get('claim_group_text', row.get('text', ''))}"
        )

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        use_reranker: bool = False,
        rerank_top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        rerank_input_top_k = max(top_k, self.rerank_input_top_k)
        output_k = rerank_top_k or top_k
        dense = self.vector_search(query, top_k=rerank_input_top_k)
        sparse = self.bm25_search(query, top_k=rerank_input_top_k)
        fused = reciprocal_rank_fusion([dense, sparse])
        for i, row in enumerate(fused, start=1):
            row["rrf_score"] = float(row.get("rrf_score", 0.0))
            row["retrieval_method"] = "rrf"
            row["original_score"] = row["rrf_score"]
            row["original_rank"] = i
            row["reranker_text"] = self._claim_reranker_text(row)

        if use_reranker:
            if self.reranker is None:
                self.reranker = CrossEncoderReranker(use_reranker=True)
            out = self.reranker.rerank(query, fused, top_k=output_k)
        else:
            out = fused[:output_k]
        for rank, row in enumerate(out, start=1):
            row["rank"] = rank
        return out
