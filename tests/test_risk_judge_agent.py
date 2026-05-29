from src.agents.risk_judge_agent import RiskJudgeAgent
from src.schemas import ListingInput
from src.listing.listing_parser import parse_listing


def test_risk_judge_basic() -> None:
    parsed = parse_listing(
        ListingInput(title="plain bottle", description="", category="home")
    )
    agent = RiskJudgeAgent()
    result = agent.judge(
        {
            "parsed_listing": parsed,
            "trademark_matches": [],
            "platform_policy_evidence": [],
            "patent_claim_evidence": [],
            "litigation_evidence": [],
        }
    )
    assert "overall_risk" in result
    assert "dimension_risks" in result
    assert result["risk_results"]
    assert result["dimension_risks"]["trademark_risk"]["risk_level"] == "low"
