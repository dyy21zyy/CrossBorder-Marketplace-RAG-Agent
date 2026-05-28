from __future__ import annotations

from src.indexing.duckdb_store import DuckDBStore

CASE_ROW_ID_CANDIDATES = ["case_row_id", "case_row", "case_id", "caseid", "case_rowid"]


def normalize_case_row_id_sql(col: str) -> str:
    return (
        "CASE "
        f"WHEN {col} IS NULL THEN '' "
        f"WHEN LOWER(TRIM(CAST({col} AS VARCHAR))) IN ('', 'nan', 'none', 'null') THEN '' "
        f"ELSE REGEXP_REPLACE(REPLACE(TRIM(CAST({col} AS VARCHAR)), ' ', ''), '\\.?0$', '') END"
    )


def normalize_patent_id_sql(col: str) -> str:
    return (
        "CASE "
        f"WHEN {col} IS NULL THEN '' "
        f"WHEN LOWER(TRIM(CAST({col} AS VARCHAR))) IN ('', 'nan', 'none', 'null') THEN '' "
        "ELSE "
        "CASE WHEN LEFT(REGEXP_REPLACE(REPLACE(REPLACE(TRIM(UPPER(CAST(" + col + " AS VARCHAR))), ' ', ''), ',', ''), '\\.?0$', ''), 2) = 'US' "
        "THEN SUBSTR(REGEXP_REPLACE(REPLACE(REPLACE(TRIM(UPPER(CAST(" + col + " AS VARCHAR))), ' ', ''), ',', ''), '\\.?0$', ''), 3) "
        "ELSE REGEXP_REPLACE(REPLACE(REPLACE(TRIM(UPPER(CAST(" + col + " AS VARCHAR))), ' ', ''), ',', ''), '\\.?0$', '') END "
        "END"
    )


def _pick_case_row_column(store: DuckDBStore, table: str) -> str:
    cols = set(store.query(f"PRAGMA table_info('{table}')")["name"].tolist())
    for candidate in CASE_ROW_ID_CANDIDATES:
        if candidate in cols:
            return candidate
    raise ValueError(f"No case row id candidate found in {table}. columns={sorted(cols)}")


def _optional_col(store: DuckDBStore, table: str, col: str) -> str:
    cols = set(store.query(f"PRAGMA table_info('{table}')")["name"].tolist())
    return col if col in cols else "NULL"


def build_litigation_tables(store: DuckDBStore, force_rebuild: bool = False) -> None:
    for t in ["raw_litigation_cases", "raw_litigation_patents", "raw_litigation_names"]:
        if not store.table_exists(t):
            raise ValueError(f"Required raw table not found: {t}")

    case_key_col = _pick_case_row_column(store, "raw_litigation_cases")
    patent_key_col = _pick_case_row_column(store, "raw_litigation_patents")
    name_key_col = _pick_case_row_column(store, "raw_litigation_names")

    if force_rebuild:
        for table in [
            "litigation_cases",
            "litigation_patents",
            "litigation_names",
            "patent_litigation_summary",
        ]:
            store.drop_table(table)

    store.execute(
        f"""
        CREATE OR REPLACE TABLE litigation_cases AS
        SELECT
          {normalize_case_row_id_sql(case_key_col)} AS case_row_id,
          {_optional_col(store, 'raw_litigation_cases', 'case_number')} AS case_number,
          {_optional_col(store, 'raw_litigation_cases', 'case_number')} AS case_number_raw,
          {_optional_col(store, 'raw_litigation_cases', 'district_id')} AS district_id,
          {_optional_col(store, 'raw_litigation_cases', 'court_name')} AS court_name,
          {_optional_col(store, 'raw_litigation_cases', 'case_name')} AS case_name,
          {_optional_col(store, 'raw_litigation_cases', 'case_cause')} AS case_cause,
          {_optional_col(store, 'raw_litigation_cases', 'jurisdictional_basis')} AS jurisdictional_basis,
          {_optional_col(store, 'raw_litigation_cases', 'date_filed')} AS date_filed,
          {_optional_col(store, 'raw_litigation_cases', 'date_closed')} AS date_closed,
          {_optional_col(store, 'raw_litigation_cases', 'settlement')} AS settlement,
          {_optional_col(store, 'raw_litigation_cases', 'case_type_1')} AS case_type_1,
          {_optional_col(store, 'raw_litigation_cases', 'case_type_2')} AS case_type_2,
          {_optional_col(store, 'raw_litigation_cases', 'case_type_3')} AS case_type_3,
          {_optional_col(store, 'raw_litigation_cases', 'case_type_note')} AS case_type_note
        FROM raw_litigation_cases
        """
    )

    store.execute(
        f"""
        CREATE OR REPLACE TABLE litigation_patents AS
        SELECT
          {normalize_case_row_id_sql(patent_key_col)} AS case_row_id,
          patent,
          {normalize_patent_id_sql('patent')} AS normalized_patent,
          {_optional_col(store, 'raw_litigation_patents', 'patent_doc_type')} AS patent_doc_type,
          {_optional_col(store, 'raw_litigation_patents', 'date_filed')} AS date_filed,
          {_optional_col(store, 'raw_litigation_patents', 'case_type_1')} AS case_type_1,
          {_optional_col(store, 'raw_litigation_patents', 'case_type_2')} AS case_type_2,
          {_optional_col(store, 'raw_litigation_patents', 'case_type_3')} AS case_type_3
        FROM raw_litigation_patents
        """
    )

    store.execute(
        f"""
        CREATE OR REPLACE TABLE litigation_names AS
        SELECT
          {normalize_case_row_id_sql(name_key_col)} AS case_row_id,
          {_optional_col(store, 'raw_litigation_names', 'party_row_count')} AS party_row_count,
          {_optional_col(store, 'raw_litigation_names', 'party_type')} AS party_type,
          {_optional_col(store, 'raw_litigation_names', 'name')} AS name,
          {_optional_col(store, 'raw_litigation_names', 'name_long')} AS name_long
        FROM raw_litigation_names
        """
    )

    store.execute(
        """
        CREATE OR REPLACE TABLE patent_litigation_summary AS
        WITH patent_case AS (
          SELECT DISTINCT p.normalized_patent, p.case_row_id
          FROM litigation_patents p
          WHERE p.normalized_patent <> '' AND p.case_row_id <> ''
        ),
        counts AS (
          SELECT
            pc.normalized_patent,
            COUNT(DISTINCT pc.case_row_id) AS case_count,
            COUNT(DISTINCT CASE WHEN CAST(c.case_type_1 AS VARCHAR) = '1' THEN pc.case_row_id END) AS infringement_case_count,
            MIN(c.date_filed) AS first_case_date,
            MAX(c.date_filed) AS latest_case_date
          FROM patent_case pc
          LEFT JOIN litigation_cases c ON c.case_row_id = pc.case_row_id
          GROUP BY pc.normalized_patent
        ),
        p_names AS (
          SELECT pc.normalized_patent, STRING_AGG(DISTINCT COALESCE(NULLIF(n.name_long, ''), n.name), ' | ') AS plaintiff_names
          FROM patent_case pc
          LEFT JOIN litigation_names n ON n.case_row_id = pc.case_row_id
          WHERE UPPER(COALESCE(n.party_type, '')) LIKE '%PLAINTIFF%'
          GROUP BY pc.normalized_patent
        ),
        d_names AS (
          SELECT pc.normalized_patent, STRING_AGG(DISTINCT COALESCE(NULLIF(n.name_long, ''), n.name), ' | ') AS defendant_names
          FROM patent_case pc
          LEFT JOIN litigation_names n ON n.case_row_id = pc.case_row_id
          WHERE UPPER(COALESCE(n.party_type, '')) LIKE '%DEFENDANT%'
          GROUP BY pc.normalized_patent
        )
        SELECT
          c.normalized_patent,
          c.case_count,
          c.infringement_case_count,
          c.first_case_date,
          c.latest_case_date,
          COALESCE(pn.plaintiff_names, '') AS plaintiff_names,
          COALESCE(dn.defendant_names, '') AS defendant_names
        FROM counts c
        LEFT JOIN p_names pn USING(normalized_patent)
        LEFT JOIN d_names dn USING(normalized_patent)
        """
    )
