from src.preprocessing.claim_group_builder import ClaimGroupBuilder


def test_build_groups_independent_with_dependents() -> None:
    rows = [
        {"patent_id": "US1", "claim_number": "1", "claim_text": "A widget.", "dependencies": "", "independent_flag": "1"},
        {"patent_id": "US1", "claim_number": "2", "claim_text": "The widget of claim 1 wherein...", "dependencies": "claim 1", "independent_flag": "0"},
    ]
    groups = ClaimGroupBuilder().build(rows)
    assert len(groups) == 1
    assert groups[0].independent_claim_number == "1"
    assert groups[0].dependent_claim_numbers == ["2"]
    assert groups[0].claim_count == 2
