"""Load USPTO patent claims data with raw/sample fallback and chunked reading."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator

import pandas as pd

FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "patent_id": ("pat_no", "patent_id", "patent", "patent_no", "patent_number"),
    "claim_text": ("claim_txt", "claim_text", "text", "claim"),
    "claim_number": ("claim_no", "claim_number"),
    "dependencies": ("dependencies", "dependency"),
    "independent_flag": ("ind_flg", "independent_flag", "is_independent"),
    "application_id": ("appl_id",),
}


def _resolve_input_dir(prefer_raw: bool = True) -> Path:
    candidates = [Path("data/raw/patent_claims"), Path("data/sample/patent_claims")]
    if not prefer_raw:
        candidates = list(reversed(candidates))
    for base in candidates:
        if base.exists():
            return base
    raise FileNotFoundError("Neither data/raw/patent_claims nor data/sample/patent_claims exists")


def _resolve_fulltext_file(input_dir: Path) -> Path:
    options = [
        input_dir / "patent_claims_fulltext.csv",
        input_dir / "patent_claims_fulltext_sample.csv",
    ]
    for path in options:
        if path.exists():
            return path
    raise FileNotFoundError(f"No claims fulltext csv found in {input_dir}")


def _normalize_columns(columns: list[str]) -> dict[str, str]:
    lowered = {c.lower().strip(): c for c in columns}
    mapping: dict[str, str] = {}
    for target, aliases in FIELD_ALIASES.items():
        for alias in aliases:
            if alias in lowered:
                mapping[target] = lowered[alias]
                break
    required = {"patent_id", "claim_text", "claim_number"}
    missing = sorted(required - set(mapping))
    if missing:
        raise ValueError(f"Missing required columns: {missing}; columns={columns}")
    return mapping


def iter_patent_claim_rows(limit: int | None = None, chunksize: int = 50_000, prefer_raw: bool = True) -> Iterator[dict[str, Any]]:
    input_dir = _resolve_input_dir(prefer_raw=prefer_raw)
    csv_path = _resolve_fulltext_file(input_dir)

    emitted = 0
    for chunk in pd.read_csv(csv_path, chunksize=chunksize):
        col_map = _normalize_columns(chunk.columns.tolist())
        selected = pd.DataFrame(
            {
                "patent_id": chunk[col_map["patent_id"]],
                "claim_number": chunk[col_map["claim_number"]],
                "claim_text": chunk[col_map["claim_text"]],
                "dependencies": chunk[col_map["dependencies"]] if "dependencies" in col_map else "",
                "independent_flag": chunk[col_map["independent_flag"]] if "independent_flag" in col_map else "",
                "application_id": chunk[col_map["application_id"]] if "application_id" in col_map else "",
            }
        )
        for row in selected.fillna("").to_dict(orient="records"):
            yield row
            emitted += 1
            if limit is not None and emitted >= limit:
                return


def load_patent_claims_df(limit: int | None = None, chunksize: int = 50_000, prefer_raw: bool = True) -> pd.DataFrame:
    rows = list(iter_patent_claim_rows(limit=limit, chunksize=chunksize, prefer_raw=prefer_raw))
    return pd.DataFrame(rows)
