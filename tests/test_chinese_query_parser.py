from src.listing.chinese_query_parser import parse_chinese_user_question


def test_parse_chinese_user_question_sample() -> None:
    parsed = parse_chinese_user_question(
        "我想在 Temu 美国站上架一款适用于 iPhone 15 的透明磁吸手机壳，没有 Apple 授权，有知识产权风险吗？"
    )

    assert parsed == {
        "title": "Phone case compatible with iPhone 15",
        "description": "Transparent magnetic phone case for iPhone 15",
        "category": "phone accessory",
        "platform": "Temu",
        "has_authorization": False,
        "enable_patent_check": True,
        "enable_litigation_check": False,
        "original_question": "我想在 Temu 美国站上架一款适用于 iPhone 15 的透明磁吸手机壳，没有 Apple 授权，有知识产权风险吗？",
        "language": "zh",
        "market": "US",
    }


def test_parse_chinese_user_question_eu_litigation_authorized() -> None:
    parsed = parse_chinese_user_question("欧盟 EUIPO 上架官方授权背包，被起诉 lawsuit 风险？")

    assert parsed["category"] == "bags"
    assert parsed["has_authorization"] is True
    assert parsed["enable_litigation_check"] is True
    assert parsed["enable_patent_check"] is False
    assert parsed["language"] == "zh"
    assert parsed["market"] == "EU"
