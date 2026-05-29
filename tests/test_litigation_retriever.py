from src.retrieval.litigation_retriever import LitigationRetriever, normalize_patent_id_literal


def test_normalize_patent_id_literal_examples() -> None:
    assert normalize_patent_id_literal("US3932328") == "3932328"
    assert normalize_patent_id_literal("3932328.0") == "3932328"
    assert normalize_patent_id_literal(" 3,932,328 ") == "3932328"
    assert normalize_patent_id_literal(None) == ""


def test_retriever_uses_single_normalized_patent_parameter() -> None:
    retriever = LitigationRetriever(":memory:")
    retriever.store.execute(
        """
        CREATE TABLE patent_litigation_summary AS
        SELECT '3932328' AS normalized_patent, 1 AS case_count
        """
    )
    retriever.store.execute(
        """
        CREATE TABLE litigation_patents AS
        SELECT 'case-1' AS case_row_id, '3932328' AS patent, '3932328' AS normalized_patent,
               'Patent' AS patent_doc_type, '2010-06-25' AS date_filed,
               '1' AS case_type_1, NULL AS case_type_2, NULL AS case_type_3
        """
    )
    retriever.store.execute(
        """
        CREATE TABLE litigation_cases AS
        SELECT 'case-1' AS case_row_id, '0:10-cv-02630' AS case_number,
               'District of Minnesota' AS court_name, '3M Company v. Avery Dennison' AS case_name,
               '2010-06-25' AS date_filed
        """
    )
    retriever.store.execute(
        """
        CREATE TABLE litigation_names AS
        SELECT 'case-1' AS case_row_id, 'Plaintiff' AS party_type,
               '3M' AS name, '3M Company' AS name_long
        """
    )

    assert retriever.get_litigation_summary("US3932328")["case_count"] == 1
    records = retriever.get_litigation_by_patent("3932328.0")
    assert len(records) == 1
    assert records[0]["normalized_patent"] == "3932328"
