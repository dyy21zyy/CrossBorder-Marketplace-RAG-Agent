from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.decision.trademark_risk import assess_trademark_risk
from src.listing.listing_parser import parse_listing
from src.retrieval.evidence_formatter import format_trademark_evidence
from src.retrieval.trademark_retriever import TrademarkRetriever
from src.retrieval.platform_retriever import PlatformPolicyRetriever
from src.schemas import ListingInput
from src.retrieval.claim_retriever import ClaimRetriever
from src.decision.litigation_risk import assess_litigation_risk
from src.retrieval.litigation_retriever import LitigationRetriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run trademark structured risk demo")
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--category", default="")
    parser.add_argument("--platform", default="")
    parser.add_argument("--has_authorization", default="false")
    parser.add_argument("--db_path", default="indexes/duckdb/trademark.duckdb")
    parser.add_argument("--enable_patent_check", default="false")
    parser.add_argument("--enable_litigation_check", default="false")
    return parser.parse_args()


def _to_bool(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "y"}


def _extract_patent_query_terms(title: str, description: str) -> str:
    text = f"{title} {description}".lower()
    words = [w.strip(",.;:()[]{}") for w in text.split()]
    terms = [w for w in words if len(w) > 3]
    return " ".join(terms[:25])


def main() -> None:
    args = parse_args()
    if not Path(args.db_path).exists():
        print("DuckDB not found. Please run first:")
        print("python scripts/01_build_trademark_db.py --sample --force_rebuild")
        return

    listing = ListingInput(
        title=args.title,
        description=args.description,
        category=args.category,
        platform=args.platform,
        has_authorization=_to_bool(args.has_authorization),
    )
    parsed = parse_listing(listing)
    retriever = TrademarkRetriever(db_path=args.db_path)
    matches = retriever.search_trademarks(parsed)
    risk = assess_trademark_risk(parsed, matches)
    evidence = [format_trademark_evidence(m.model_dump()) for m in matches]

    print("=== Parsed Listing ===")
    print(parsed.model_dump_json(indent=2, ensure_ascii=False))
    print("\n=== Candidate brand terms ===")
    print(json.dumps(parsed.candidate_brand_terms, ensure_ascii=False, indent=2))
    print("\n=== Risk patterns ===")
    print(json.dumps(parsed.risk_patterns, ensure_ascii=False, indent=2))
    print("\n=== Trademark matches ===")
    print(json.dumps([m.model_dump() for m in matches], ensure_ascii=False, indent=2))
    print("\n=== Trademark risk ===")
    print(risk.model_dump_json(indent=2, ensure_ascii=False))
    print("\n=== Evidence ===")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))

    if risk.risk_level.lower() in {"high", "medium"}:
        policy_query = "Temu intellectual property trademark infringement report enforcement"
        policy_retriever = PlatformPolicyRetriever()
        policy_evidence = policy_retriever.hybrid_search(policy_query)
        policy_output = [
            {
                "source": e.source,
                "section": e.metadata.get("section"),
                "page": f"{e.metadata.get('page_start')}-{e.metadata.get('page_end')}",
                "chunk_text": e.snippet,
                "score": e.score,
            }
            for e in policy_evidence
        ]
        print("\n=== Platform policy evidence ===")
        print(json.dumps(policy_output, ensure_ascii=False, indent=2))

    if _to_bool(args.enable_patent_check):
        query = _extract_patent_query_terms(args.title, args.description)
        try:
            claim_retriever = ClaimRetriever()
            claim_hits = claim_retriever.hybrid_search(query, top_k=5)
        except Exception as exc:  # noqa: BLE001
            claim_hits = [{"error": str(exc)}]

        patent_claim_risk = {
            "risk_type": "patent_claim",
            "note": "发现相关权利要求，需要人工核验；本结果不构成法律意见。",
            "query": query,
            "retrieval_count": len(claim_hits),
            "evidence": claim_hits,
        }
        print("\n=== Patent claim risk (screening) ===")
        print(json.dumps(patent_claim_risk, ensure_ascii=False, indent=2))

        patent_ids = []
        for hit in claim_hits:
            pid = str(hit.get("patent_id", "")).strip() if isinstance(hit, dict) else ""
            if pid:
                patent_ids.append(pid)

        if _to_bool(args.enable_litigation_check) and patent_ids:
            litigation = assess_litigation_risk(patent_ids=sorted(set(patent_ids)), retriever=LitigationRetriever())
            party_evidence = []
            lr = LitigationRetriever()
            for pid in sorted(set(patent_ids)):
                rows = lr.get_litigation_by_patent(pid)[:20]
                party_evidence.append({"patent_id": pid, "cases": rows})
            print("\n=== Patent litigation summary (structured) ===")
            print(json.dumps(litigation, ensure_ascii=False, indent=2))
            print("\n=== Patent litigation party evidence ===")
            print(json.dumps(party_evidence, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
