from src.listing.listing_parser import parse_listing
from src.schemas import ListingInput


def test_parse_listing_risk_patterns() -> None:
    parsed = parse_listing(
        ListingInput(
            title="Phone case compatible with iPhone 15",
            description="Inspired by Apple style design, works with MagSafe",
            category="phone accessory",
            platform="Temu",
            has_authorization=False,
        )
    )
    assert parsed.title
    assert "iphone" in " ".join(parsed.candidate_brand_terms).lower()
    rp = " | ".join(parsed.risk_patterns).lower()
    assert "compatible with" in rp
    assert "inspired by" in rp
    assert "works with" in rp
