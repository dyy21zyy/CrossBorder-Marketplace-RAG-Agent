from __future__ import annotations

import logging
from typing import Any

from src.indexing.duckdb_store import DuckDBStore

logger = logging.getLogger(__name__)


def normalize_patent_id_literal(patent_id: object) -> str:
    """Normalize a single patent id value without SQL placeholders."""
    if patent_id is None:
        return ""

    normalized = str(patent_id).strip()
    if normalized.lower() in {"", "nan", "none", "<na>", "null"}:
        return ""

    normalized = normalized.upper().replace(" ", "").replace(",", "")
    if normalized.endswith(".0"):
        normalized = normalized[:-2]
    if normalized.startswith("US"):
        normalized = normalized[2:]

    if normalized.lower() in {"", "nan", "none", "<na>", "null"}:
        return ""
    return normalized


class LitigationRetriever:
    def __init__(self, db_path: str = "indexes/duckdb/litigation.duckdb") -> None:
        self.store = DuckDBStore(db_path)

    def _normalize_patent_literal(self, patent_id: str) -> str:
        return normalize_patent_id_literal(patent_id)

    def get_litigation_by_patent(self, patent_id: str) -> list[dict[str, Any]]:
        norm = self._normalize_patent_literal(patent_id)
        if not norm:
            return []
        try:
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
        except Exception as exc:
            logger.warning("Failed to query litigation records for patent %s: %s", norm, exc)
            return []
        return df.to_dict(orient="records")

    def get_litigation_summary(self, patent_id: str) -> dict[str, Any]:
        norm = self._normalize_patent_literal(patent_id)
        if not norm:
            return {}
        try:
            df = self.store.query("SELECT * FROM patent_litigation_summary WHERE normalized_patent = ?", [norm])
        except Exception as exc:
            logger.warning("Failed to query litigation summary for patent %s: %s", norm, exc)
            return {}
        return {} if df.empty else df.iloc[0].to_dict()

    def search_party_litigation(self, name: str) -> list[dict[str, Any]]:
        q = (name or "").strip().upper()
        if not q:
            return []
        try:
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
        except Exception as exc:
            logger.warning("Failed to query party litigation for %s: %s", q, exc)
            return []
        return df.to_dict(orient="records")

    def get_frequent_plaintiffs(self, limit: int = 50) -> list[dict[str, Any]]:
        try:
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
        except Exception as exc:
            logger.warning("Failed to query frequent plaintiffs: %s", exc)
            return []
        return df.to_dict(orient="records")
