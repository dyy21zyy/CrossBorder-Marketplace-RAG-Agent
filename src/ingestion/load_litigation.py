from __future__ import annotations

import logging
from pathlib import Path

from src.indexing.duckdb_store import DuckDBStore

logger = logging.getLogger(__name__)


_TABLE_TO_CSV_BASENAME = {
    "cases": "cases",
    "patents": "patents",
    "names": "names",
}


def _pick_csv(base_dir: Path, basename: str) -> Path:
    primary = base_dir / f"{basename}.csv"
    sample = base_dir / f"{basename}_sample.csv"
    if primary.exists():
        return primary
    if sample.exists():
        return sample
    raise FileNotFoundError(f"Missing litigation CSV under {base_dir}: {primary.name} or {sample.name}")


def resolve_litigation_files(mode: str | None) -> tuple[Path, dict[str, Path]]:
    root = Path("data")
    raw_dir = root / "raw" / "litigation"
    sample_dir = root / "sample" / "litigation"

    if mode == "sample":
        base_dir = sample_dir
    elif mode == "full":
        base_dir = raw_dir
    else:
        base_dir = raw_dir if raw_dir.exists() else sample_dir

    if not base_dir.exists():
        raise FileNotFoundError(f"Litigation directory not found: {base_dir}")

    files = {k: _pick_csv(base_dir, v) for k, v in _TABLE_TO_CSV_BASENAME.items()}
    logger.info("Using litigation dataset dir: %s", base_dir)
    return base_dir, files


def load_litigation_raw_tables(
    store: DuckDBStore,
    files: dict[str, Path],
    force_rebuild: bool = False,
) -> None:
    mapping = {
        "cases": "raw_litigation_cases",
        "patents": "raw_litigation_patents",
        "names": "raw_litigation_names",
    }

    for key, table in mapping.items():
        if force_rebuild:
            store.drop_table(table)
        if store.table_exists(table):
            logger.info("Skip existing table: %s", table)
            continue
        path = files[key]
        logger.info("Loading %s from %s", table, path)
        store.execute(
            f"""
            CREATE TABLE {table} AS
            SELECT *
            FROM read_csv_auto(?, header=true, all_varchar=true, ignore_errors=false)
            """,
            [str(path)],
        )
