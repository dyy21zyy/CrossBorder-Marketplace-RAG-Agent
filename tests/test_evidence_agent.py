from src.agents.evidence_agent import EvidenceAgent
from src.schemas import ListingInput


def test_evidence_agent_collect_shape() -> None:
    agent = EvidenceAgent()
    bundle = agent.collect(
        ListingInput(
            title="iPhone case",
            description="magnetic stand",
            category="phone",
            platform="Temu",
        ),
        routed_intents=[
            "trademark_risk",
            "platform_policy",
            "patent_claim_risk",
            "litigation_risk",
        ],
        enable_patent_check=False,
        enable_litigation_check=False,
    )
    assert "parsed_listing" in bundle
    assert "trademark_evidence" in bundle
    assert "platform_policy_evidence" in bundle
    assert bundle["patent_claim_evidence"] == []


def test_evidence_agent_rewrites_chinese_original_question() -> None:
    question = "我想在 Temu 美国站上架一款适用于 iPhone 15 的透明磁吸手机壳，没有 Apple 授权，有风险吗？"
    bundle = EvidenceAgent().collect(
        ListingInput(
            title="Phone case compatible with iPhone 15",
            description="Transparent magnetic phone case for iPhone 15",
            category="phone accessory",
            platform="Temu",
            original_question=question,
        ),
        routed_intents=["trademark_risk"],
        enable_patent_check=False,
        enable_litigation_check=False,
    )

    assert bundle["original_question"] == question
    assert bundle["answer_language"] == "zh"
    assert "transparent phone case" in bundle["retrieval_query_en"]
    assert "Apple" in bundle["parsed_listing"].candidate_brand_terms
