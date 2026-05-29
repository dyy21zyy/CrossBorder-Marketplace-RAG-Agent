from src.agents.listing_rewrite_agent import ListingRewriteAgent
from src.schemas import ListingInput, ParsedListing


def _rewrite(
    title: str,
    category: str = "",
    has_authorization: bool = False,
    brands: list[str] | None = None,
):
    agent = ListingRewriteAgent()
    listing = ListingInput(
        title=title, category=category, has_authorization=has_authorization
    )
    evidence_bundle = {
        "parsed_listing": ParsedListing(
            normalized_title="",
            normalized_description="",
            candidate_brand_terms=brands or [],
        )
    }
    return agent.rewrite(listing, {"overall_risk": "medium"}, evidence_bundle)


def test_listing_rewrite_removes_risky_words():
    out = _rewrite(
        "Official Replica style case compatible with iPhone 15",
        category="phone accessory",
        brands=["iphone"],
    )
    assert 2 <= len(out) <= 3
    joined = " ".join(x["title"].lower() for x in out)
    assert "replica" not in joined
    assert "official" not in joined
    assert "style" not in joined


def test_chinese_iphone_15_rewrites_model_as_complete_generic_phrase():
    out = _rewrite(
        "适用于 iPhone 15 的透明磁吸手机壳", category="手机配件", brands=["iPhone"]
    )

    assert [item["title"] for item in out] == [
        "透明磁吸手机保护壳",
        "适用于部分 6.1 英寸机型的手机保护壳",
        "通用磁吸手机壳",
    ]
    assert all("iPhone" not in item["title"] for item in out)
    assert all("15 透明" not in item["title"] for item in out)
    assert all(
        any("\u4e00" <= char <= "\u9fff" for char in item["reason"]) for item in out
    )


def test_english_nike_style_replaces_brand_and_removes_risky_style():
    out = _rewrite(
        "Nike style lightweight running shoes", category="footwear", brands=["Nike"]
    )
    joined_titles = " ".join(item["title"].lower() for item in out)
    joined_reasons = " ".join(item["reason"] for item in out)

    assert "nike" not in joined_titles
    assert "style" not in joined_titles
    assert "running shoes" in joined_titles
    assert not any("\u4e00" <= char <= "\u9fff" for char in joined_reasons)


def test_english_lego_compatible_uses_interlocking_building_blocks():
    out = _rewrite(
        "LEGO compatible building blocks set", category="toy", brands=["LEGO"]
    )
    joined_titles = " ".join(item["title"].lower() for item in out)

    assert "lego" not in joined_titles
    assert "interlocking building blocks" in joined_titles


def test_chinese_disney_cartoon_outputs_chinese_generic_cartoon_wording():
    out = _rewrite("Disney cartoon 儿童背包", category="背包", brands=["Disney"])
    joined_titles = " ".join(item["title"] for item in out)

    assert "Disney" not in joined_titles
    assert "卡通" in joined_titles
    assert all(
        any("\u4e00" <= char <= "\u9fff" for char in item["reason"]) for item in out
    )


def test_authorized_listing_can_keep_cautious_compatible_but_not_official():
    out = _rewrite(
        "Official phone case compatible with iPhone 15",
        category="phone accessory",
        has_authorization=True,
        brands=["iPhone"],
    )
    joined_titles = " ".join(item["title"].lower() for item in out)

    assert "compatible with iphone 15" in joined_titles
    assert "official" not in joined_titles
    assert "authorized" not in joined_titles
    assert "genuine" not in joined_titles
    assert "authentic" not in joined_titles
