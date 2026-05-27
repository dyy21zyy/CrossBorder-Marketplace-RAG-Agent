from pathlib import Path

from src.indexing.duckdb_store import DuckDBStore
from src.ingestion.load_trademark import load_trademark_raw_tables
from src.preprocessing.trademark_builder import build_trademark_tables, create_trademark_indexes


def test_build_trademark_tables(tmp_path: Path) -> None:
    fixture_dir = Path("tests/fixtures/trademark")
    files = {
        "case_file": fixture_dir / "case_file_sample.csv",
        "owner": fixture_dir / "owner_sample.csv",
        "intl_class": fixture_dir / "intl_class_sample.csv",
        "statement": fixture_dir / "statement_sample.csv",
    }
    store = DuckDBStore(tmp_path / "trademark.duckdb")
    store.connect()

    load_trademark_raw_tables(store, files, force_rebuild=True)
    build_trademark_tables(store, force_rebuild=True)
    create_trademark_indexes(store)

    case = store.query("SELECT serial_no, normalized_mark FROM trademark_case ORDER BY serial_no")
    owner = store.query("SELECT serial_no, normalized_owner FROM trademark_owner ORDER BY serial_no")
    st = store.query("SELECT statement_type_cd FROM trademark_statement ORDER BY statement_type_cd")

    assert case.loc[0, "normalized_mark"] == "ACME ROCKET"
    assert case.loc[1, "normalized_mark"] == ""
    assert owner.loc[0, "normalized_owner"] == "ACME CORP"
    assert owner.loc[1, "normalized_owner"] == ""
    assert st["statement_type_cd"].tolist() == ["CC001", "GS001"]
