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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run trademark structured risk demo")
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--category", default="")
    parser.add_argument("--platform", default="")
    parser.add_argument("--has_authorization", default="false")
    parser.add_argument("--db_path", default="indexes/duckdb/trademark.duckdb")
    return parser.parse_args()


def _to_bool(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "y"}


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


if __name__ == "__main__":
    main()
