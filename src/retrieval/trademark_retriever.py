from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz

from src.indexing.duckdb_store import DuckDBStore
from src.schemas import ParsedListing, TrademarkMatch


class TrademarkRetriever:
    def __init__(self, db_path: str = "indexes/duckdb/trademark.duckdb") -> None:
        self.store = DuckDBStore(db_path)

    @staticmethod
    def _normalize_mark(term: str) -> str:
        return re.sub(r"\s+", " ", (term or "").strip().upper())

    def exact_match_mark(self, term: str) -> list[dict[str, Any]]:
        norm = self._normalize_mark(term)
        if not norm:
            return []
        df = self.store.query(
            """
            SELECT serial_no, registration_no, mark_id_char, cfh_status_cd
            FROM trademark_case
            WHERE normalized_mark = ?
            LIMIT 20
            """,
            [norm],
        )
        return df.to_dict(orient="records")

    def fuzzy_match_mark(self, term: str, threshold: int = 90, limit: int = 10) -> list[dict[str, Any]]:
        norm = self._normalize_mark(term)
        if not norm:
            return []
        # bound candidates for larger datasets
        candidates = self.store.query(
            """
            SELECT serial_no, registration_no, mark_id_char, cfh_status_cd
            FROM trademark_case
            WHERE mark_id_char IS NOT NULL AND mark_id_char <> ''
            LIMIT 5000
            """
        ).to_dict(orient="records")

        scored: list[tuple[float, dict[str, Any]]] = []
        for row in candidates:
            score = float(fuzz.ratio(norm, self._normalize_mark(str(row.get("mark_id_char", "")))))
            if score >= threshold:
                scored.append((score, row))
        scored.sort(key=lambda x: x[0], reverse=True)
        out: list[dict[str, Any]] = []
        for score, row in scored[:limit]:
            row = dict(row)
            row["match_score"] = score
            out.append(row)
        return out

    def get_trademark_details(self, serial_no: str) -> dict[str, Any]:
        owners = self.store.query("SELECT own_name FROM trademark_owner WHERE serial_no = ? LIMIT 10", [serial_no])
        classes = self.store.query("SELECT intl_class_cd FROM trademark_class WHERE serial_no = ? LIMIT 20", [serial_no])
        statements = self.store.query(
            "SELECT statement_text FROM trademark_statement WHERE serial_no = ? LIMIT 20", [serial_no]
        )
        return {
            "owners": [str(x) for x in owners["own_name"].dropna().tolist()],
            "intl_classes": [str(x) for x in classes["intl_class_cd"].dropna().tolist()],
            "statements": [str(x) for x in statements["statement_text"].dropna().tolist()],
        }

    def search_trademarks(self, parsed_listing: ParsedListing) -> list[TrademarkMatch]:
        terms = parsed_listing.candidate_brand_terms or parsed_listing.brand_terms
        matches: list[TrademarkMatch] = []
        seen: set[tuple[str, str, str]] = set()
        for term in terms:
            for row in self.exact_match_mark(term):
                detail = self.get_trademark_details(str(row["serial_no"]))
                key = (term.lower(), str(row["serial_no"]), "exact")
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    TrademarkMatch(
                        term=term,
                        serial_no=str(row.get("serial_no", "")),
                        mark_id_char=str(row.get("mark_id_char", "")),
                        registration_no=str(row.get("registration_no", "")),
                        status=str(row.get("cfh_status_cd", "")),
                        owners=detail["owners"],
                        intl_classes=detail["intl_classes"],
                        statements=detail["statements"],
                        match_type="exact",
                        match_score=100.0,
                        mark=str(row.get("mark_id_char", "")),
                        owner=", ".join(detail["owners"]),
                        serial_number=str(row.get("serial_no", "")),
                        registration_number=str(row.get("registration_no", "")),
                        classes=detail["intl_classes"],
                        similarity=100.0,
                    )
                )
            for row in self.fuzzy_match_mark(term):
                detail = self.get_trademark_details(str(row["serial_no"]))
                key = (term.lower(), str(row["serial_no"]), "fuzzy")
                if key in seen:
                    continue
                seen.add(key)
                matches.append(
                    TrademarkMatch(
                        term=term,
                        serial_no=str(row.get("serial_no", "")),
                        mark_id_char=str(row.get("mark_id_char", "")),
                        registration_no=str(row.get("registration_no", "")),
                        status=str(row.get("cfh_status_cd", "")),
                        owners=detail["owners"],
                        intl_classes=detail["intl_classes"],
                        statements=detail["statements"],
                        match_type="fuzzy",
                        match_score=float(row.get("match_score", 0.0)),
                        mark=str(row.get("mark_id_char", "")),
                        owner=", ".join(detail["owners"]),
                        serial_number=str(row.get("serial_no", "")),
                        registration_number=str(row.get("registration_no", "")),
                        classes=detail["intl_classes"],
                        similarity=float(row.get("match_score", 0.0)),
                    )
                )
        return matches
