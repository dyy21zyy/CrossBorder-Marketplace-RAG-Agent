from src.agents.listing_rewrite_agent import ListingRewriteAgent
from src.schemas import ListingInput, ParsedListing


def test_listing_rewrite_removes_risky_words():
    agent = ListingRewriteAgent()
    listing = ListingInput(title="Official Replica style case compatible with iPhone 15", category="phone accessory", has_authorization=False)
    evidence_bundle = {"parsed_listing": ParsedListing(normalized_title="", normalized_description="", candidate_brand_terms=["iphone"])}
    out = agent.rewrite(listing, {"overall_risk": "medium"}, evidence_bundle)
    assert 2 <= len(out) <= 3
    joined = " ".join(x["title"].lower() for x in out)
    assert "replica" not in joined
    assert "official" not in joined
    assert "style" not in joined
