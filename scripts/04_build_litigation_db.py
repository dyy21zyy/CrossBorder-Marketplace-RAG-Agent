from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.indexing.duckdb_store import DuckDBStore
from src.ingestion.load_litigation import load_litigation_raw_tables, resolve_litigation_files
from src.preprocessing.litigation_builder import build_litigation_tables


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Build litigation structured DuckDB")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--sample", action="store_true")
    mode.add_argument("--full", action="store_true")
    p.add_argument("--limit", type=int, default=None, help="not applicable for DuckDB table build; reserved for interface consistency")
    p.add_argument("--batch_size", type=int, default=None, help="not applicable for DuckDB read_csv_auto load; reserved for interface consistency")
    p.add_argument("--resume", action="store_true", help="not applicable for idempotent DuckDB build; reserved for interface consistency")
    p.add_argument("--force_rebuild", action="store_true")
    p.add_argument("--db_path", default="indexes/duckdb/litigation.duckdb")
    return p.parse_args()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    args = parse_args()
    if args.limit is not None or args.batch_size is not None or args.resume:
        logging.info("--limit/--batch_size/--resume are not applicable for litigation DuckDB build; arguments are ignored")
    mode = "sample" if args.sample else "full" if args.full else None
    _, files = resolve_litigation_files(mode=mode)

    db_path = Path(args.db_path)
    store = DuckDBStore(db_path)
    store.connect()

    load_litigation_raw_tables(store, files=files, force_rebuild=args.force_rebuild)
    build_litigation_tables(store, force_rebuild=args.force_rebuild)

    for table in [
        "raw_litigation_cases",
        "raw_litigation_patents",
        "raw_litigation_names",
        "litigation_cases",
        "litigation_patents",
        "litigation_names",
        "patent_litigation_summary",
    ]:
        cnt = int(store.query(f"SELECT COUNT(*) AS c FROM {table}").iloc[0]["c"])
        logging.info("%s: %s", table, cnt)


if __name__ == "__main__":
    main()
