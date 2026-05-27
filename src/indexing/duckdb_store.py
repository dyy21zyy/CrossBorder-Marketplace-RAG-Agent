from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

logger = logging.getLogger(__name__)


class DuckDBStore:
    """Simple DuckDB wrapper for structured retrieval workloads."""

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.conn: duckdb.DuckDBPyConnection | None = None

    def connect(self) -> duckdb.DuckDBPyConnection:
        if self.conn is not None:
            return self.conn
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        logger.info("Connecting DuckDB at %s", self.db_path)
        self.conn = duckdb.connect(str(self.db_path))
        return self.conn

    def execute(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> None:
        conn = self.connect()
        logger.debug("Execute SQL: %s", sql)
        if params is None:
            conn.execute(sql)
        else:
            conn.execute(sql, params)

    def query(self, sql: str, params: list[Any] | tuple[Any, ...] | None = None) -> pd.DataFrame:
        conn = self.connect()
        logger.debug("Query SQL: %s", sql)
        if params is None:
            return conn.execute(sql).fetchdf()
        return conn.execute(sql, params).fetchdf()

    def table_exists(self, table_name: str) -> bool:
        df = self.query(
            """
            SELECT COUNT(*) AS cnt
            FROM information_schema.tables
            WHERE table_schema = 'main' AND table_name = ?
            """,
            [table_name],
        )
        return bool(df.iloc[0]["cnt"])

    def drop_table(self, table_name: str) -> None:
        logger.info("Dropping table if exists: %s", table_name)
        self.execute(f"DROP TABLE IF EXISTS {table_name}")

    def create_index(self, index_sql: str) -> None:
        logger.info("Creating index: %s", index_sql)
        self.execute(index_sql)

    def close(self) -> None:
        if self.conn is not None:
            logger.info("Closing DuckDB connection")
            self.conn.close()
            self.conn = None
