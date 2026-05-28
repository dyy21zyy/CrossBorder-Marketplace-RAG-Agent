from pathlib import Path

from src.indexing.duckdb_store import DuckDBStore
from src.ingestion.load_litigation import load_litigation_raw_tables
from src.preprocessing.litigation_builder import build_litigation_tables


def test_build_litigation_tables_sample() -> None:
    base = Path("data/sample/litigation")
    files = {
        "cases": base / "cases_sample.csv",
        "patents": base / "patents_sample.csv",
        "names": base / "names_sample.csv",
    }
    store = DuckDBStore(":memory:")
    store.connect()
    load_litigation_raw_tables(store, files, force_rebuild=True)
    build_litigation_tables(store, force_rebuild=True)

    cases = int(store.query("SELECT COUNT(*) c FROM litigation_cases").iloc[0]["c"])
    patents = int(store.query("SELECT COUNT(*) c FROM litigation_patents WHERE normalized_patent <> ''").iloc[0]["c"])
    summary = int(store.query("SELECT COUNT(*) c FROM patent_litigation_summary").iloc[0]["c"])

    assert cases > 0
    assert patents > 0
    assert summary > 0
