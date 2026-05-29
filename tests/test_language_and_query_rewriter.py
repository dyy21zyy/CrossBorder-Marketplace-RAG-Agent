from src.retrieval.query_rewriter import rewrite_query_for_retrieval
from src.utils.language import detect_language


def test_detect_language_zh_when_contains_chinese() -> None:
    assert detect_language("iPhone 手机壳") == "zh"
    assert detect_language("phone case") == "en"


def test_rewrite_chinese_query_for_english_retrieval_preserves_brands() -> None:
    query = rewrite_query_for_retrieval(
        "我想在 Temu 美国站上架一款适用于 iPhone 15 的透明磁吸手机壳，没有 Apple 授权，有风险吗？"
    )

    assert "transparent phone case" in query
    assert "magnetic" in query
    assert "compatible with" in query
    assert "iPhone 15" in query
    assert "Apple" in query
    assert "authorization" in query
