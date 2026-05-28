from src.decision.trademark_risk import assess_trademark_risk
from src.schemas import ParsedListing, TrademarkMatch


def test_assess_trademark_risk_high() -> None:
    parsed = ParsedListing(
        normalized_title="Phone case compatible with iPhone 15",
        normalized_description="for iphone",
        title="Phone case compatible with iPhone 15",
        description="for iphone",
        category="phone accessory",
        has_authorization=False,
        candidate_brand_terms=["iPhone"],
        risk_patterns=["compatible with iPhone"],
    )
    matches = [
        TrademarkMatch(
            term="iPhone",
            serial_no="1",
            mark_id_char="IPHONE",
            status="LIVE/REGISTERED",
            intl_classes=["009"],
            match_type="exact",
            match_score=100,
        )
    ]
    risk = assess_trademark_risk(parsed, matches)
    assert risk.risk_level == "high"
    assert any("exact_match" in rule for rule in risk.triggered_rules)
