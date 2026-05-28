from src.decision.litigation_risk import assess_litigation_risk


class DummyRetriever:
    def __init__(self, summaries: dict[str, dict]):
        self.summaries = summaries

    def get_litigation_summary(self, patent_id: str):
        return self.summaries.get(patent_id, {})


def test_assess_litigation_risk_levels() -> None:
    retriever = DummyRetriever(
        {
            "P1": {"normalized_patent": "P1", "case_count": 0, "infringement_case_count": 0},
            "P2": {"normalized_patent": "P2", "case_count": 2, "infringement_case_count": 0},
            "P3": {"normalized_patent": "P3", "case_count": 3, "infringement_case_count": 1},
        }
    )

    risk = assess_litigation_risk(["P0", "P1", "P2", "P3"], retriever=retriever)
    levels = {x["patent_id"]: x["litigation_risk"] for x in risk["results"]}

    assert levels["P0"] == "low"
    assert levels["P2"] == "medium"
    assert levels["P3"] == "high"
    assert risk["overall_risk"] == "high"
