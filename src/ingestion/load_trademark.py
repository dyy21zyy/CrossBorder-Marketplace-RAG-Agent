from __future__ import annotations

import logging
from pathlib import Path

from src.indexing.duckdb_store import DuckDBStore

logger = logging.getLogger(__name__)


def _pick_csv(base_dir: Path, name: str) -> Path:
    primary = base_dir / f"{name}.csv"
    sample = base_dir / f"{name}_sample.csv"
    if primary.exists():
        return primary
    if sample.exists():
        return sample
    raise FileNotFoundError(f"Missing trademark CSV under {base_dir}: {primary.name} or {sample.name}")


def resolve_trademark_files(mode: str | None) -> dict[str, Path]:
    root = Path("data")
    raw_dir = root / "raw" / "trademark"
    sample_dir = root / "sample" / "trademark"

    if mode == "sample":
        base = sample_dir
    elif mode == "full":
        base = raw_dir
    else:
        base = raw_dir if raw_dir.exists() else sample_dir

    if not base.exists():
        raise FileNotFoundError(f"Trademark directory not found: {base}")

    files = {
        "case_file": _pick_csv(base, "case_file"),
        "owner": _pick_csv(base, "owner"),
        "intl_class": _pick_csv(base, "intl_class"),
        "statement": _pick_csv(base, "statement"),
    }
    logger.info("Using trademark dataset dir: %s", base)
    return files


def load_trademark_raw_tables(
    store: DuckDBStore,
    files: dict[str, Path],
    force_rebuild: bool = False,
) -> None:
    mapping = {
        "case_file": "raw_case_file",
        "owner": "raw_owner",
        "intl_class": "raw_intl_class",
        "statement": "raw_statement",
    }
    for key, table in mapping.items():
        path = files[key]
        if force_rebuild:
            store.drop_table(table)
        if store.table_exists(table):
            logger.info("Skip existing table: %s", table)
            continue
        logger.info("Loading %s from %s", table, path)
        sql = f"""
            CREATE TABLE {table} AS
            SELECT *
            FROM read_csv_auto(?, header=true, all_varchar=true, ignore_errors=false)
        """
        store.execute(sql, [str(path)])
