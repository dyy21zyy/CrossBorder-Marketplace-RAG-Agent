from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

from src.listing.listing_parser import parse_listing
from src.retrieval.query_rewriter import (
    extract_preserved_brand_terms,
    rewrite_query_for_retrieval,
)
from src.schemas import EvidenceItem, ListingInput
from src.utils.language import detect_language

PATENT_KEYWORDS = (
    "patent",
    "claim",
    "structure",
    "mechanism",
    "foldable",
    "magnetic",
    "holder",
    "stand",
    "专利",
    "结构",
    "折叠",
    "磁吸",
    "支架",
)


class EvidenceAgent:
    def __init__(
        self,
        trademark_retriever: Any | None = None,
        platform_policy_retriever: Any | None = None,
        claim_retriever: Any | None = None,
        litigation_retriever: Any | None = None,
    ) -> None:
        self.trademark_retriever = trademark_retriever
        self.platform_policy_retriever = platform_policy_retriever
        self.claim_retriever = claim_retriever
        self.litigation_retriever = litigation_retriever

    @staticmethod
    def _has_patent_signal(text: str) -> bool:
        lowered = (text or "").lower()
        return any(keyword in lowered for keyword in PATENT_KEYWORDS)

    @staticmethod
    def _elapsed_ms(started_at: float) -> float:
        return round((time.perf_counter() - started_at) * 1000, 2)

    def collect(
        self,
        listing_input: ListingInput,
        routed_intents: list[str],
        enable_patent_check: bool = True,
        enable_litigation_check: bool = True,
        use_reranker: bool = False,
        top_k: int = 5,
        rerank_input_top_k: int | None = None,
        rerank_top_k: int | None = None,
        answer_language: str = "auto",
        progress_callback: Callable[[str], None] | None = None,
    ) -> dict:
        def progress(message: str) -> None:
            if progress_callback is not None:
                progress_callback(message)

        progress("正在解析问题")
        metrics: dict[str, Any] = {
            "parsing_latency": 0.0,
            "trademark_latency": 0.0,
            "platform_policy_latency": 0.0,
            "patent_claim_latency": 0.0,
            "litigation_latency": 0.0,
            "reranker_latency": 0.0,
        }
        parsing_started_at = time.perf_counter()
        parsed = parse_listing(listing_input)
        original_question = (
            listing_input.original_question
            or f"{listing_input.title} {listing_input.description}".strip()
        ).strip()
        input_language = detect_language(original_question)
        resolved_answer_language = (answer_language or "auto").strip().lower()
        if resolved_answer_language not in {"auto", "zh", "en"}:
            resolved_answer_language = "auto"
        if resolved_answer_language == "auto":
            resolved_answer_language = "zh" if input_language == "zh" else "en"
        retrieval_query_en = (
            rewrite_query_for_retrieval(original_question, target_language="en")
            if input_language == "zh"
            else f"{parsed.normalized_title} {parsed.normalized_description}".strip()
        )
        if input_language == "zh":
            for brand in extract_preserved_brand_terms(original_question):
                if brand.lower() not in {
                    x.lower() for x in parsed.candidate_brand_terms
                }:
                    parsed.candidate_brand_terms.append(brand)
                    parsed.brand_terms.append(brand)
        metrics["parsing_latency"] = self._elapsed_ms(parsing_started_at)
        trademark_matches = []
        trademark_evidence: list[EvidenceItem] = []
        platform_evidence: list[EvidenceItem] = []
        claim_evidence: list[EvidenceItem] = []
        litigation_evidence: list[EvidenceItem] = []

        progress("正在检索商标")
        trademark_started_at = time.perf_counter()
        from src.retrieval.trademark_retriever import TrademarkRetriever

        try:
            tm = self.trademark_retriever or TrademarkRetriever()
            trademark_matches = tm.search_trademarks(parsed)
            trademark_evidence = [
                m.evidence for m in trademark_matches if m.evidence is not None
            ]
        except Exception:  # noqa: BLE001
            trademark_evidence = [
                EvidenceItem(
                    evidence_id="tm-missing",
                    evidence_type="system",
                    source="trademark",
                    snippet="Please run python scripts/01_build_trademark_db.py first.",
                )
            ]
        metrics["trademark_latency"] = self._elapsed_ms(trademark_started_at)

        if "platform_policy" in routed_intents:
            progress("正在检索平台规则")
            platform_started_at = time.perf_counter()
            from src.retrieval.platform_retriever import PlatformPolicyRetriever

            try:
                pr = self.platform_policy_retriever or PlatformPolicyRetriever()
                if rerank_input_top_k is not None:
                    pr.rerank_input_top_k = rerank_input_top_k
                if rerank_top_k is not None:
                    pr.rerank_top_k = rerank_top_k
                platform_evidence = pr.hybrid_search(
                    retrieval_query_en,
                    top_k=top_k,
                    use_reranker=use_reranker,
                    rerank_top_k=rerank_top_k,
                )
            except Exception:  # noqa: BLE001
                platform_evidence = [
                    EvidenceItem(
                        evidence_id="platform-missing",
                        evidence_type="system",
                        source="platform_policy",
                        snippet="Please run python scripts/02_build_platform_index.py first.",
                    )
                ]
            metrics["platform_policy_latency"] = self._elapsed_ms(platform_started_at)
            metrics["reranker_latency"] += (
                float(getattr(pr, "last_metrics", {}).get("reranker_latency", 0.0))
                if "pr" in locals()
                else 0.0
            )

        patent_ids: list[str] = []
        patent_signal_text = " ".join(
            [
                original_question,
                retrieval_query_en,
                parsed.normalized_title,
                parsed.normalized_description,
                listing_input.category or "",
            ]
        )
        should_run_patent_claim = (
            enable_patent_check
            and "patent_claim_risk" in routed_intents
            and self._has_patent_signal(patent_signal_text)
        )
        if should_run_patent_claim:
            progress("正在检索专利 claim")
            from src.retrieval.claim_retriever import ClaimRetriever

            try:
                claim_started_at = time.perf_counter()
                cr = self.claim_retriever or ClaimRetriever()
                if rerank_input_top_k is not None:
                    cr.rerank_input_top_k = rerank_input_top_k
                if rerank_top_k is not None:
                    cr.rerank_top_k = rerank_top_k
                raw = cr.hybrid_search(
                    retrieval_query_en,
                    top_k=top_k,
                    use_reranker=use_reranker,
                    rerank_top_k=rerank_top_k,
                )
                for i, item in enumerate(raw):
                    patent_id = str(
                        item.get("patent_id")
                        or item.get("metadata", {}).get("patent_id", "")
                    )
                    if patent_id:
                        patent_ids.append(patent_id)
                    metadata = dict(item.get("metadata", {}))
                    metadata.update(
                        {
                            "retrieval_method": item.get(
                                "retrieval_method",
                                metadata.get("retrieval_method", "rrf"),
                            ),
                            "rrf_score": item.get(
                                "rrf_score", metadata.get("rrf_score")
                            ),
                            "reranker_score": item.get(
                                "reranker_score", metadata.get("reranker_score")
                            ),
                            "reranker_rank": item.get(
                                "reranker_rank", metadata.get("reranker_rank")
                            ),
                            "rank": item.get("rank", i + 1),
                        }
                    )
                    claim_evidence.append(
                        EvidenceItem(
                            evidence_id=str(item.get("chunk_id", f"claim-{i}")),
                            evidence_type="patent_claim",
                            source=str(item.get("source", "claim_groups")),
                            title=(
                                f"Patent {patent_id}" if patent_id else "Patent claim"
                            ),
                            snippet=str(item.get("text", "")),
                            score=float(
                                item.get(
                                    "reranker_score",
                                    item.get("rrf_score", item.get("score", 0.0)),
                                )
                            ),
                            metadata=metadata,
                        )
                    )
            except Exception:  # noqa: BLE001
                claim_evidence = [
                    EvidenceItem(
                        evidence_id="claim-missing",
                        evidence_type="system",
                        source="patent_claim",
                        snippet="Please run python scripts/03_build_claim_index.py first.",
                    )
                ]
            metrics["patent_claim_latency"] = (
                self._elapsed_ms(claim_started_at)
                if "claim_started_at" in locals()
                else 0.0
            )
            metrics["reranker_latency"] += (
                float(getattr(cr, "last_metrics", {}).get("reranker_latency", 0.0))
                if "cr" in locals()
                else 0.0
            )

        has_claim_evidence = any(e.evidence_type != "system" for e in claim_evidence)
        if enable_litigation_check and has_claim_evidence and patent_ids:
            progress("正在查询诉讼记录")
            from src.retrieval.litigation_retriever import LitigationRetriever

            try:
                litigation_started_at = time.perf_counter()
                lr = self.litigation_retriever or LitigationRetriever()
                for pid in sorted(set(patent_ids)):
                    summary = lr.get_litigation_summary(pid)
                    if summary:
                        litigation_evidence.append(
                            EvidenceItem(
                                evidence_id=f"lit-{pid}",
                                evidence_type="litigation",
                                source="litigation_summary",
                                title=f"Patent {pid}",
                                snippet=f"case_count={summary.get('case_count', 0)}, infringement_case_count={summary.get('infringement_case_count', 0)}",
                                score=float(summary.get("case_count", 0)),
                                metadata=summary,
                            )
                        )
            except Exception:  # noqa: BLE001
                litigation_evidence = [
                    EvidenceItem(
                        evidence_id="litigation-missing",
                        evidence_type="system",
                        source="litigation",
                        snippet="Please run python scripts/04_build_litigation_db.py first.",
                    )
                ]
            metrics["litigation_latency"] = (
                self._elapsed_ms(litigation_started_at)
                if "litigation_started_at" in locals()
                else 0.0
            )

        return {
            "parsed_listing": parsed,
            "original_question": original_question,
            "retrieval_query_en": retrieval_query_en,
            "answer_language": resolved_answer_language,
            "routed_intents": routed_intents,
            "skipped_patent_claim": not should_run_patent_claim,
            "skipped_litigation": not (
                enable_litigation_check and has_claim_evidence and patent_ids
            ),
            "metrics": metrics,
            "trademark_matches": trademark_matches,
            "trademark_evidence": trademark_evidence,
            "platform_policy_evidence": platform_evidence,
            "patent_claim_evidence": claim_evidence,
            "litigation_evidence": litigation_evidence,
        }
