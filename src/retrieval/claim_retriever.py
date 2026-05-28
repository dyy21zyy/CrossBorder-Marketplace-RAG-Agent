"""Claim-level hybrid retriever using Chroma + BM25 + RRF."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

from src.indexing.bm25_index import bm25_search as bm25_lookup
from src.indexing.bm25_index import build_bm25_index, load_bm25_index
from src.indexing.chroma_store import build_chroma_index, load_chroma_collection, vector_search
from src.preprocessing.claim_group_builder import ClaimGroup
from src.retrieval.rrf_fusion import reciprocal_rank_fusion


class ClaimRetriever:
    def __init__(self, chroma_dir: str = "indexes/chroma", bm25_path: str = "indexes/bm25/claim_groups.pkl", collection_name: str = "claim_groups") -> None:
        self.chroma_dir = chroma_dir
        self.bm25_path = bm25_path
        self.collection_name = collection_name
        self.collection = None
        self.bm25_data: dict[str, Any] | None = None

    def build_claim_documents(self, claim_groups: list[ClaimGroup]) -> list[dict[str, Any]]:
        docs: list[dict[str, Any]] = []
        for idx, cg in enumerate(claim_groups):
            docs.append(
                {
                    "chunk_id": f"{cg.patent_id}_{cg.independent_claim_number}_{idx}",
                    "text": cg.claim_group_text,
                    "source": cg.source,
                    "section": "patent_claim_group",
                    "metadata": asdict(cg),
                    "patent_id": cg.patent_id,
                    "independent_claim_number": cg.independent_claim_number,
                }
            )
        return docs

    def build_indexes(self, claim_groups: list[ClaimGroup]) -> None:
        docs = self.build_claim_documents(claim_groups)
        self.collection = build_chroma_index(docs, persist_dir=self.chroma_dir, collection_name=self.collection_name)
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

    def hybrid_search(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        dense = self.vector_search(query, top_k=top_k)
        sparse = self.bm25_search(query, top_k=top_k)
        return reciprocal_rank_fusion([dense, sparse])[:top_k]
