from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indexing.duckdb_store import DuckDBStore
from src.ingestion.load_trademark import load_trademark_raw_tables, resolve_trademark_files
from src.preprocessing.trademark_builder import build_trademark_tables, create_trademark_indexes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build USPTO trademark structured DuckDB")
    parser.add_argument("--sample", action="store_true", help="force sample mode")
    parser.add_argument("--full", action="store_true", help="force full/raw mode")
    parser.add_argument("--force_rebuild", action="store_true", help="drop and rebuild tables")
    return parser.parse_args()


def _mode_from_args(args: argparse.Namespace) -> str | None:
    if args.sample and args.full:
        raise ValueError("--sample and --full cannot be used together")
    if args.sample:
        return "sample"
    if args.full:
        return "full"
    return None


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    args = parse_args()
    mode = _mode_from_args(args)

    store = DuckDBStore("indexes/duckdb/trademark.duckdb")
    try:
        store.connect()
        files = resolve_trademark_files(mode)
        load_trademark_raw_tables(store, files, force_rebuild=args.force_rebuild)
        build_trademark_tables(store, force_rebuild=args.force_rebuild)
        create_trademark_indexes(store)

        tables = [
            "raw_case_file", "raw_owner", "raw_intl_class", "raw_statement",
            "trademark_case", "trademark_owner", "trademark_class", "trademark_statement",
        ]
        for t in tables:
            cnt = int(store.query(f"SELECT COUNT(*) AS c FROM {t}").iloc[0]["c"])
            logging.info("Table %s row count: %s", t, cnt)
    finally:
        store.close()


if __name__ == "__main__":
    main()
