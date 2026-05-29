from src.agents.final_answer_agent import FinalAnswerAgent
from src.schemas import EvidenceItem, ListingInput


def test_final_answer_contains_disclaimer_and_no_legal_conclusion():
    agent = FinalAnswerAgent()
    listing = ListingInput(
        title="Phone case compatible with iPhone 15", has_authorization=False
    )
    evidence_bundle = {
        "trademark_evidence": [
            EvidenceItem(
                evidence_id="1",
                evidence_type="trademark",
                source="uspto",
                snippet="iphone mark",
                score=0.9,
                metadata={},
            )
        ],
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
    result = agent.generate(
        listing,
        evidence_bundle,
        risk,
        [{"title": "Magnetic phone case", "reason": "neutral"}],
    )
    assert "does not constitute legal advice" in result.summary
    assert "the product infringes" not in result.summary.lower()
    assert result.risk_results
    assert result.risk_results[0].risk_level == "medium"


def test_final_answer_uses_chinese_template_for_chinese_question() -> None:
    agent = FinalAnswerAgent()
    listing = ListingInput(
        title="Phone case compatible with iPhone 15",
        original_question="我想在 Temu 美国站上架一款适用于 iPhone 15 的透明磁吸手机壳，没有 Apple 授权，有风险吗？",
    )
    evidence_bundle = {
        "original_question": listing.original_question,
        "retrieval_query_en": "transparent phone case magnetic compatible with iPhone 15 Apple authorization",
        "answer_language": "zh",
        "trademark_evidence": [],
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

    result = agent.generate(listing, evidence_bundle, risk, [], answer_language="auto")

    assert "总体风险" in result.summary
    assert "商标风险" in result.summary
    assert "本系统仅用于知识产权风险初筛，不构成法律意见。" in result.summary
    assert result.disclaimers == ["本系统仅用于知识产权风险初筛，不构成法律意见。"]
