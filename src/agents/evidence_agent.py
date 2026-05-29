from __future__ import annotations

from src.listing.listing_parser import parse_listing
from src.schemas import EvidenceItem, ListingInput


class EvidenceAgent:
    def collect(
        self,
        listing_input: ListingInput,
        routed_intents: list[str],
        enable_patent_check: bool = True,
        enable_litigation_check: bool = True,
        use_reranker: bool = False,
    ) -> dict:
        parsed = parse_listing(listing_input)
        trademark_matches = []
        trademark_evidence: list[EvidenceItem] = []
        platform_evidence: list[EvidenceItem] = []
        claim_evidence: list[EvidenceItem] = []
        litigation_evidence: list[EvidenceItem] = []

        try:
            from src.retrieval.trademark_retriever import TrademarkRetriever

            tm = TrademarkRetriever()
            trademark_matches = tm.search_trademarks(parsed)
            trademark_evidence = [m.evidence for m in trademark_matches if m.evidence is not None]
        except Exception:  # noqa: BLE001
            trademark_evidence = [EvidenceItem(evidence_id="tm-missing", evidence_type="system", source="trademark", snippet="Please run python scripts/01_build_trademark_db.py first.")]

        if "platform_policy" in routed_intents:
            try:
                from src.retrieval.platform_retriever import PlatformPolicyRetriever

                pr = PlatformPolicyRetriever()
                query = f"{parsed.normalized_title} {parsed.normalized_description}".strip()
                platform_evidence = pr.hybrid_search(query, top_k=5, use_reranker=use_reranker)
            except Exception:  # noqa: BLE001
                platform_evidence = [EvidenceItem(evidence_id="platform-missing", evidence_type="system", source="platform_policy", snippet="Please run python scripts/02_build_platform_index.py first.")]

        patent_ids: list[str] = []
        if enable_patent_check and "patent_claim_risk" in routed_intents:
            try:
                from src.retrieval.claim_retriever import ClaimRetriever

                cr = ClaimRetriever()
                query = f"{parsed.normalized_title} {parsed.normalized_description}".strip()
                raw = cr.hybrid_search(query, top_k=5, use_reranker=use_reranker)
                for i, item in enumerate(raw):
                    patent_id = str(item.get("patent_id") or item.get("metadata", {}).get("patent_id", ""))
                    if patent_id:
                        patent_ids.append(patent_id)
                    metadata = dict(item.get("metadata", {}))
                    metadata.update({
                        "retrieval_method": item.get("retrieval_method", metadata.get("retrieval_method", "rrf")),
                        "rrf_score": item.get("rrf_score", metadata.get("rrf_score")),
                        "reranker_score": item.get("reranker_score", metadata.get("reranker_score")),
                        "reranker_rank": item.get("reranker_rank", metadata.get("reranker_rank")),
                        "rank": item.get("rank", i + 1),
                    })
                    claim_evidence.append(EvidenceItem(evidence_id=str(item.get("chunk_id", f"claim-{i}")), evidence_type="patent_claim", source=str(item.get("source", "claim_groups")), title=f"Patent {patent_id}" if patent_id else "Patent claim", snippet=str(item.get("text", "")), score=float(item.get("reranker_score", item.get("rrf_score", item.get("score", 0.0)))), metadata=metadata))
            except Exception:  # noqa: BLE001
                claim_evidence = [EvidenceItem(evidence_id="claim-missing", evidence_type="system", source="patent_claim", snippet="Please run python scripts/03_build_claim_index.py first.")]

        if enable_litigation_check and ("litigation_risk" in routed_intents or patent_ids):
            try:
                from src.retrieval.litigation_retriever import LitigationRetriever

                lr = LitigationRetriever()
                for pid in sorted(set(patent_ids)):
                    summary = lr.get_litigation_summary(pid)
                    if summary:
                        litigation_evidence.append(EvidenceItem(evidence_id=f"lit-{pid}", evidence_type="litigation", source="litigation_summary", title=f"Patent {pid}", snippet=f"case_count={summary.get('case_count', 0)}, infringement_case_count={summary.get('infringement_case_count', 0)}", score=float(summary.get("case_count", 0)), metadata=summary))
            except Exception:  # noqa: BLE001
                litigation_evidence = [EvidenceItem(evidence_id="litigation-missing", evidence_type="system", source="litigation", snippet="Please run python scripts/04_build_litigation_db.py first.")]

        return {
            "parsed_listing": parsed,
            "routed_intents": routed_intents,
            "trademark_matches": trademark_matches,
            "trademark_evidence": trademark_evidence,
            "platform_policy_evidence": platform_evidence,
            "patent_claim_evidence": claim_evidence,
            "litigation_evidence": litigation_evidence,
        }
