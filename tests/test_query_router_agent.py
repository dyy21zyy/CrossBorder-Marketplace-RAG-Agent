from src.agents.query_router_agent import QueryRouter


def test_query_router_rules() -> None:
    router = QueryRouter()
    result = router.route("Please rewrite safer title for compatible with iPhone charger")
    assert "listing_rewrite" in result["intents"]
    assert "trademark_risk" in result["intents"]
