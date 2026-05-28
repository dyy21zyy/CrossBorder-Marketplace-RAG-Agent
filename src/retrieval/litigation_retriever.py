from __future__ import annotations

from typing import Any

from src.indexing.duckdb_store import DuckDBStore
from src.preprocessing.litigation_builder import normalize_patent_id_sql


class LitigationRetriever:
    def __init__(self, db_path: str = "indexes/duckdb/litigation.duckdb") -> None:
        self.store = DuckDBStore(db_path)

    def _normalize_patent_literal(self, patent_id: str) -> str:
        df = self.store.query(f"SELECT {normalize_patent_id_sql('?')} AS p", [patent_id])
        return str(df.iloc[0]["p"])

    def get_litigation_by_patent(self, patent_id: str) -> list[dict[str, Any]]:
        norm = self._normalize_patent_literal(patent_id)
        if not norm:
            return []
        df = self.store.query(
            """
            SELECT p.*, c.case_number, c.court_name, c.case_name, c.date_filed AS case_date_filed,
                   n.party_type, n.name, n.name_long
            FROM litigation_patents p
            LEFT JOIN litigation_cases c ON c.case_row_id = p.case_row_id
            LEFT JOIN litigation_names n ON n.case_row_id = p.case_row_id
            WHERE p.normalized_patent = ?
            ORDER BY c.date_filed DESC
            LIMIT 500
            """,
            [norm],
        )
        return df.to_dict(orient="records")

    def get_litigation_summary(self, patent_id: str) -> dict[str, Any]:
        norm = self._normalize_patent_literal(patent_id)
        if not norm:
            return {}
        df = self.store.query("SELECT * FROM patent_litigation_summary WHERE normalized_patent = ?", [norm])
        return {} if df.empty else df.iloc[0].to_dict()

    def search_party_litigation(self, name: str) -> list[dict[str, Any]]:
        q = (name or "").strip().upper()
        if not q:
            return []
        df = self.store.query(
            """
            SELECT n.case_row_id, n.party_type, n.name, n.name_long,
                   c.case_number, c.case_name, c.court_name, c.date_filed
            FROM litigation_names n
            LEFT JOIN litigation_cases c ON c.case_row_id = n.case_row_id
            WHERE UPPER(COALESCE(n.name_long, '')) LIKE '%' || ? || '%'
               OR UPPER(COALESCE(n.name, '')) LIKE '%' || ? || '%'
            ORDER BY c.date_filed DESC
            LIMIT 200
            """,
            [q, q],
        )
        return df.to_dict(orient="records")

    def get_frequent_plaintiffs(self, limit: int = 50) -> list[dict[str, Any]]:
        df = self.store.query(
            """
            SELECT COALESCE(NULLIF(name_long, ''), name) AS plaintiff_name,
                   COUNT(DISTINCT case_row_id) AS case_count
            FROM litigation_names
            WHERE UPPER(COALESCE(party_type, '')) LIKE '%PLAINTIFF%'
              AND COALESCE(NULLIF(name_long, ''), name) IS NOT NULL
              AND COALESCE(NULLIF(name_long, ''), name) <> ''
            GROUP BY 1
            ORDER BY case_count DESC, plaintiff_name ASC
            LIMIT ?
            """,
            [limit],
        )
        return df.to_dict(orient="records")
