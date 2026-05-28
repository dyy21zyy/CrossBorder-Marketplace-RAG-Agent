from src.agents.final_answer_agent import FinalAnswerAgent
from src.schemas import EvidenceItem, ListingInput


def test_final_answer_contains_disclaimer_and_no_legal_conclusion():
    agent = FinalAnswerAgent()
    listing = ListingInput(title="Phone case compatible with iPhone 15", has_authorization=False)
    evidence_bundle = {
        "trademark_evidence": [EvidenceItem(evidence_id="1", evidence_type="trademark", source="uspto", snippet="iphone mark", score=0.9, metadata={})],
        "platform_policy_evidence": [],
        "patent_claim_evidence": [],
        "litigation_evidence": [],
    }
    risk = {
        "overall_risk": "medium",
        "dimension_risks": {
            "trademark_risk": "medium",
            "platform_policy_risk": "unknown",
            "patent_claim_risk": "unknown",
            "litigation_risk": "unknown",
        },
    }
    result = agent.generate(listing, evidence_bundle, risk, [{"title": "Magnetic phone case", "reason": "neutral"}])
    assert "does not constitute legal advice" in result.summary
    assert "the product infringes" not in result.summary.lower()
