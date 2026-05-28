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

INDEX_HINTS = {
    "trademark": "python scripts/01_build_trademark_db.py --sample --force_rebuild",
    "platform_policy": "python scripts/02_build_platform_index.py",
    "patent_claim": "python scripts/03_build_claim_index.py --sample --limit 50000",
    "litigation": "python scripts/04_build_litigation_db.py --sample --force_rebuild",
}


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


def _print_json_section(title: str, payload: object) -> None:
    print(f"\n=== {title} ===")
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _print_index_hints(evidence_bundle: dict) -> None:
    missing: list[tuple[str, str]] = []
    mapping = {
        "trademark_evidence": "trademark",
        "platform_policy_evidence": "platform_policy",
        "patent_claim_evidence": "patent_claim",
        "litigation_evidence": "litigation",
    }
    for key, source in mapping.items():
        for item in evidence_bundle.get(key, []):
            if getattr(item, "evidence_type", "") == "system" and "Please run" in getattr(item, "snippet", ""):
                missing.append((source, INDEX_HINTS[source]))
                break

    if missing:
        print("\n=== Missing Index Hints ===")
        for source, cmd in missing:
            print(f"- Missing {source} index. Run: {cmd}")


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

    _print_json_section("Parsed Listing", evidence_bundle["parsed_listing"].model_dump())
    _print_json_section("Routed Intents", routed)
    _print_json_section("Trademark Matches", [x.model_dump() for x in evidence_bundle.get("trademark_matches", [])])
    _print_json_section("Platform Policy Evidence", [x.model_dump() for x in evidence_bundle.get("platform_policy_evidence", [])])
    _print_json_section("Patent Claim Evidence", [x.model_dump() for x in evidence_bundle.get("patent_claim_evidence", [])])
    _print_json_section("Litigation Evidence", [x.model_dump() for x in evidence_bundle.get("litigation_evidence", [])])
    _print_json_section("Risk Results", risk)
    _print_json_section("Listing Rewrite Suggestions", rewrite)
    _print_json_section("Final Answer", answer.model_dump())
    _print_json_section("Disclaimer", {"disclaimer": answer.disclaimers[0] if answer.disclaimers else ""})

    _print_index_hints(evidence_bundle)


if __name__ == "__main__":
    main()
