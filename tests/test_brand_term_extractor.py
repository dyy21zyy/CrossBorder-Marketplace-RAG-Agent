from src.listing.brand_term_extractor import extract_candidate_brand_terms


def test_extract_brand_terms() -> None:
    terms = extract_candidate_brand_terms(
        "Phone case compatible with iPhone 15",
        "Magnetic transparent case for Apple AirPods Pro and LEGO style toy",
    )
    lowered = {t.lower() for t in terms}
    assert any(t.startswith("iphone 15") for t in lowered)
    assert "apple" in lowered
    assert "airpods pro" in lowered or "airpods" in lowered
    assert "lego" in lowered
    assert "case" not in lowered
