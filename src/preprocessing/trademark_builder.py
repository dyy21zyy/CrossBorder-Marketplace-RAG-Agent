from __future__ import annotations

import logging

from src.indexing.duckdb_store import DuckDBStore

logger = logging.getLogger(__name__)


_REQUIRED_COLUMNS = {
    "raw_case_file": [
        "serial_no", "registration_no", "mark_id_char", "mark_draw_cd", "filing_dt",
        "registration_dt", "cfh_status_cd", "cfh_status_dt", "trade_mark_in",
        "serv_mark_in", "std_char_claim_in",
    ],
    "raw_owner": [
        "serial_no", "own_name", "own_type_cd", "own_entity_cd", "own_addr_country_cd", "own_nalty_country_cd",
    ],
    "raw_intl_class": ["serial_no", "class_id", "intl_class_cd"],
    "raw_statement": ["serial_no", "statement_type_cd", "statement_text"],
}


def _ensure_columns(store: DuckDBStore, table: str, required: list[str]) -> None:
    cols_df = store.query(f"PRAGMA table_info('{table}')")
    cols = set(cols_df["name"].tolist())
    missing = [c for c in required if c not in cols]
    if missing:
        raise ValueError(
            f"Table '{table}' missing columns: {missing}. Actual columns: {sorted(cols)}"
        )


def _normalize_sql(col: str) -> str:
    return f"COALESCE(TRIM(REGEXP_REPLACE(UPPER({col}), '\\s+', ' ')), '')"


def build_trademark_tables(store: DuckDBStore, force_rebuild: bool = False) -> None:
    for table, cols in _REQUIRED_COLUMNS.items():
        if not store.table_exists(table):
            raise ValueError(f"Required raw table not found: {table}")
        _ensure_columns(store, table, cols)

    derived = ["trademark_case", "trademark_owner", "trademark_class", "trademark_statement"]
    if force_rebuild:
        for t in derived:
            store.drop_table(t)

    store.execute(
        f"""
        CREATE OR REPLACE TABLE trademark_case AS
        SELECT
          serial_no,
          registration_no,
          mark_id_char,
          {_normalize_sql('mark_id_char')} AS normalized_mark,
          mark_draw_cd,
          filing_dt,
          registration_dt,
          cfh_status_cd,
          cfh_status_dt,
          trade_mark_in,
          serv_mark_in,
          std_char_claim_in
        FROM raw_case_file
        """
    )

    store.execute(
        f"""
        CREATE OR REPLACE TABLE trademark_owner AS
        SELECT
          serial_no,
          own_name,
          {_normalize_sql('own_name')} AS normalized_owner,
          own_type_cd,
          own_entity_cd,
          own_addr_country_cd,
          own_nalty_country_cd
        FROM raw_owner
        """
    )

    store.execute(
        """
        CREATE OR REPLACE TABLE trademark_class AS
        SELECT serial_no, class_id, intl_class_cd
        FROM raw_intl_class
        """
    )

    store.execute(
        """
        CREATE OR REPLACE TABLE trademark_statement AS
        SELECT serial_no, statement_type_cd, statement_text
        FROM raw_statement
        WHERE statement_type_cd LIKE 'GS%'
           OR statement_type_cd LIKE 'DM%'
           OR statement_type_cd LIKE 'PM%'
           OR statement_type_cd LIKE 'D0%'
           OR statement_type_cd LIKE 'D1%'
           OR statement_type_cd LIKE 'CC%'
           OR statement_type_cd LIKE 'CD%'
        """
    )


def create_trademark_indexes(store: DuckDBStore) -> None:
    index_sqls = [
        "CREATE INDEX IF NOT EXISTS idx_trademark_case_serial_no ON trademark_case(serial_no)",
        "CREATE INDEX IF NOT EXISTS idx_trademark_case_normalized_mark ON trademark_case(normalized_mark)",
        "CREATE INDEX IF NOT EXISTS idx_trademark_owner_serial_no ON trademark_owner(serial_no)",
        "CREATE INDEX IF NOT EXISTS idx_trademark_class_serial_no ON trademark_class(serial_no)",
        "CREATE INDEX IF NOT EXISTS idx_trademark_statement_serial_no ON trademark_statement(serial_no)",
        "CREATE INDEX IF NOT EXISTS idx_trademark_statement_type_cd ON trademark_statement(statement_type_cd)",
    ]
    for sql in index_sqls:
        store.create_index(sql)
        logger.info("Index created: %s", sql)
