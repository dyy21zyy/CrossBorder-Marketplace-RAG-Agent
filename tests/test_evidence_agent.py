from src.agents.evidence_agent import EvidenceAgent
from src.schemas import ListingInput


def test_evidence_agent_collect_shape() -> None:
    agent = EvidenceAgent()
    bundle = agent.collect(
        ListingInput(title="iPhone case", description="magnetic stand", category="phone", platform="Temu"),
        routed_intents=["trademark_risk", "platform_policy", "patent_claim_risk", "litigation_risk"],
        enable_patent_check=False,
        enable_litigation_check=False,
    )
    assert "parsed_listing" in bundle
    assert "trademark_evidence" in bundle
    assert "platform_policy_evidence" in bundle
    assert bundle["patent_claim_evidence"] == []
