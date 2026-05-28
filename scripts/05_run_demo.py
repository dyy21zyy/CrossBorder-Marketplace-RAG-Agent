from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.agents.evidence_agent import EvidenceAgent
from src.agents.final_answer_agent import FinalAnswerAgent
from src.agents.listing_rewrite_agent import ListingRewriteAgent
from src.agents.query_router_agent import QueryRouter
from src.agents.risk_judge_agent import RiskJudgeAgent
from src.schemas import ListingInput


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run full LLM+RAG screening demo")
    p.add_argument("--title", required=True)
    p.add_argument("--description", default="")
    p.add_argument("--category", default="")
    p.add_argument("--platform", default="")
    p.add_argument("--has_authorization", default="false")
    p.add_argument("--enable_patent_check", default="false")
    p.add_argument("--enable_litigation_check", default="false")
    p.add_argument("--mock_llm", default="true")
    return p.parse_args()


def _to_bool(s: str) -> bool:
    return str(s).strip().lower() in {"1", "true", "yes", "y"}


def main() -> None:
    args = parse_args()
    os.environ["MOCK_LLM"] = "true" if _to_bool(args.mock_llm) else "false"

    listing = ListingInput(
        title=args.title,
        description=args.description,
        category=args.category,
        platform=args.platform,
        has_authorization=_to_bool(args.has_authorization),
    )

    query = f"{listing.title} {listing.description} {listing.category} {listing.platform}"
    routed = QueryRouter().route(query)
    evidence_bundle = EvidenceAgent().collect(
        listing_input=listing,
        routed_intents=routed.get("intents", []),
        enable_patent_check=_to_bool(args.enable_patent_check),
        enable_litigation_check=_to_bool(args.enable_litigation_check),
    )
    risk = RiskJudgeAgent().judge(evidence_bundle)
    rewrite = ListingRewriteAgent().rewrite(listing, risk, evidence_bundle)
    answer = FinalAnswerAgent().generate(listing, evidence_bundle, risk, rewrite)

    print("=== Parsed Listing ===")
    print(evidence_bundle["parsed_listing"].model_dump_json(indent=2, ensure_ascii=False))
    print("\n=== Routed Intents ===")
    print(json.dumps(routed, ensure_ascii=False, indent=2))
    print("\n=== Evidence Summary ===")
    summary = {
        "trademark": len(evidence_bundle.get("trademark_evidence", [])),
        "platform": len(evidence_bundle.get("platform_policy_evidence", [])),
        "patent_claim": len(evidence_bundle.get("patent_claim_evidence", [])),
        "litigation": len(evidence_bundle.get("litigation_evidence", [])),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n=== Risk Results ===")
    print(json.dumps(risk, ensure_ascii=False, indent=2))
    print("\n=== Rewrite Suggestions ===")
    print(json.dumps(rewrite, ensure_ascii=False, indent=2))
    print("\n=== Final Answer ===")
    print(answer.model_dump_json(indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
