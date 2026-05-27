from __future__ import annotations

import argparse
import json
import random
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Sequence, Set, Tuple
from zipfile import ZipFile

import pandas as pd

RISK_BRANDS = [
    "APPLE", "IPHONE", "AIRPODS", "DISNEY", "MARVEL", "LEGO", "NIKE", "ADIDAS", "STANLEY", "CROCS",
    "BARBIE", "POKEMON", "HELLO KITTY", "SAMSUNG", "DYSON", "GOPRO", "LOUIS VUITTON", "GUCCI",
    "PRADA", "CHANEL", "HERMES", "ROLEX", "PLAYSTATION", "NINTENDO", "TESLA", "BMW", "MERCEDES",
    "PAW PATROL", "PEPPA PIG", "HARRY POTTER",
]
PRODUCT_KEYWORDS = [
    "case", "holder", "stand", "magnetic", "foldable", "charger", "wireless", "battery", "glove",
    "grooming", "vacuum", "bottle", "tumbler", "block", "toy", "shoe", "backpack", "dryer",
    "phone", "mobile", "cover", "container", "cup",
    "phone case", "magnetic holder", "phone stand", "foldable stand", "ring holder",
    "wireless charger", "heated glove", "battery glove", "pet grooming", "vacuum",
    "tumbler", "water bottle", "toy building block", "shoe sole", "backpack", "hair dryer",
]
STATEMENT_PREFIXES = ("GS", "DM", "PM", "D0", "D1", "CC", "CD")
DOC_KEYWORDS = ["complaint", "settlement", "dismissal", "judgment", "claim construction", "summary judgment"]
CASE_ROW_ID_CANDIDATES = ["case_row_id", "case_row", "case_id", "caseid", "case_rowid"]


def warn(msg: str) -> None:
    print(f"[WARNING] {msg}")


def info(msg: str) -> None:
    print(f"[INFO] {msg}")


def find_data_file(base_dir: Path, expected_stem: str) -> Optional[Path]:
    if not base_dir.exists():
        warn(f"Directory not found: {base_dir}")
        return None

    stem = expected_stem.lower()
    candidates = [p for p in base_dir.rglob("*") if p.is_file() and stem in p.stem.lower()]
    if not candidates:
        return None

    def rank(path: Path) -> Tuple[int, int, str]:
        suffix = path.suffix.lower()
        if suffix == ".csv":
            t = 0
        elif suffix == ".zip":
            t = 1
        elif suffix == ".pdf":
            t = 2
        else:
            t = 3
        exact = 0 if path.stem.lower() == stem else 1
        return (t, exact, str(path).lower())

    return sorted(candidates, key=rank)[0]


def iter_csv_chunks(file_path: Path, chunksize: int) -> Iterator[pd.DataFrame]:
    suffix = file_path.suffix.lower()

    def _yield_csv(reader_source) -> Iterator[pd.DataFrame]:
        try:
            yield from pd.read_csv(reader_source, chunksize=chunksize, low_memory=False, encoding="utf-8")
        except UnicodeDecodeError:
            yield from pd.read_csv(reader_source, chunksize=chunksize, low_memory=False, encoding="latin1")

    if suffix == ".csv":
        yield from _yield_csv(file_path)
    elif suffix == ".zip":
        with ZipFile(file_path) as zf:
            inner_csv = next((n for n in zf.namelist() if n.lower().endswith(".csv")), None)
            if not inner_csv:
                raise FileNotFoundError(f"No CSV found inside zip: {file_path}")
            with zf.open(inner_csv) as f:
                yield from _yield_csv(f)
    else:
        raise ValueError(f"Unsupported CSV container: {file_path}")


def pick_column(columns: Sequence[str], candidates: Sequence[str]) -> Optional[str]:
    m = {c.lower(): c for c in columns}
    for c in candidates:
        if c.lower() in m:
            return m[c.lower()]
    return None


def normalize_patent_id(v: object) -> str:
    s = _normalize_text_like(v).upper().replace(" ", "").replace(",", "").replace(".0", "")
    if s.startswith("US"):
        s = s[2:]
    return s


def _normalize_text_like(v: object) -> str:
    if pd.isna(v):
        return ""
    s = str(v).strip()
    if s.lower() in {"", "nan", "none", "<na>"}:
        return ""
    return s


def normalize_case_row_id(v: object) -> object:
    def _norm_one(x: object) -> str:
        s = _normalize_text_like(x).replace(" ", "").replace(".0", "")
        return s

    if isinstance(v, pd.Series):
        return v.map(_norm_one)
    return _norm_one(v)


def find_case_row_col(df: pd.DataFrame) -> str:
    col = pick_column(df.columns, CASE_ROW_ID_CANDIDATES)
    if col:
        return col
    cols = list(df.columns)
    warn(f"Cannot detect case row id column. Available columns: {cols}")
    raise ValueError("Missing case row id column. Expected one of: " + ", ".join(CASE_ROW_ID_CANDIDATES))


def detect_patent_fields(columns: Sequence[str]) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str], Optional[str]]:
    patent_id_field = pick_column(columns, [
        "pat_no", "patent_id", "patent", "patent_no", "patent_number", "doc_id", "document_id", "appl_id"
    ])
    claim_text_field = pick_column(columns, [
        "claim_txt", "claim_text", "text", "claim", "claims_text", "claim_text_original"
    ])
    claim_no_field = pick_column(columns, ["claim_no", "claim_number", "claim_num"])
    dependency_field = pick_column(columns, ["dependencies", "dependency", "depends_on"])
    independent_field = pick_column(columns, ["ind_flg", "independent_flag", "is_independent"])
    return patent_id_field, claim_text_field, claim_no_field, dependency_field, independent_field


def append_csv(path: Path, df: pd.DataFrame, state: Dict[str, bool]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    header = not state.get(str(path), False)
    df.to_csv(path, mode="a", index=False, header=header)
    state[str(path)] = True


def extract_trademark(args, out_dir: Path, manifest: Dict, write_state: Dict[str, bool]) -> Set[str]:
    td = Path(args.trademark_dir)
    targets = {k: find_data_file(td, k) for k in ["case_file", "owner", "intl_class", "statement"]}
    for k, v in targets.items():
        if not v:
            warn(f"Trademark source missing: {k}")

    serials: Set[str] = set()
    case_out = out_dir / "trademark" / "case_file_sample.csv"
    case_rows = 0
    if targets["case_file"]:
        mark_col = None
        serial_col = None
        pat = re.compile("|".join(re.escape(b) for b in RISK_BRANDS), flags=re.IGNORECASE)
        for chunk in iter_csv_chunks(targets["case_file"], args.chunksize):
            if mark_col is None:
                mark_col = pick_column(chunk.columns, ["mark_id_char", "mark_text", "mark", "mark_identification", "word_mark"])
                serial_col = pick_column(chunk.columns, ["serial_no", "serial_number", "serialnum"])
                if not mark_col or not serial_col:
                    warn(f"Cannot detect trademark columns. Available columns: {list(chunk.columns)}")
                    break
            mask = chunk[mark_col].astype(str).str.contains(pat, na=False)
            matched = chunk[mask]
            if matched.empty:
                continue
            for _, row in matched.iterrows():
                if case_rows >= args.max_trademark_cases:
                    break
                serial_val = str(row[serial_col])
                serials.add(serial_val)
                append_csv(case_out, pd.DataFrame([row]), write_state)
                case_rows += 1
            if case_rows >= args.max_trademark_cases:
                break
    info(f"trademark/case_file_sample.csv rows={case_rows}")
    manifest[str(case_out)] = {"rows": case_rows, "source": str(targets.get("case_file") or "")}

    def filter_by_serial(src: Optional[Path], out: Path, max_rows: Optional[int] = None, statement=False):
        rows = 0
        if not src or not serials:
            manifest[str(out)] = {"rows": rows, "source": str(src or "")}
            info(f"{out.relative_to(out_dir)} rows={rows}")
            return
        serial_col = None
        stmt_col = None
        for chunk in iter_csv_chunks(src, args.chunksize):
            if serial_col is None:
                serial_col = pick_column(chunk.columns, ["serial_no", "serial_number", "serialnum"])
                stmt_col = pick_column(chunk.columns, ["statement_type_cd"]) if statement else None
                if not serial_col:
                    warn(f"Cannot detect serial column for {src}. Columns: {list(chunk.columns)}")
                    break
            filtered = chunk[chunk[serial_col].astype(str).isin(serials)]
            if statement and stmt_col:
                filtered = filtered[filtered[stmt_col].astype(str).str.upper().str.startswith(STATEMENT_PREFIXES, na=False)]
            if filtered.empty:
                continue
            if max_rows is not None and rows + len(filtered) > max_rows:
                filtered = filtered.head(max_rows - rows)
            append_csv(out, filtered, write_state)
            rows += len(filtered)
            if max_rows is not None and rows >= max_rows:
                break
        info(f"{out.relative_to(out_dir)} rows={rows}")
        manifest[str(out)] = {"rows": rows, "source": str(src)}

    filter_by_serial(targets["owner"], out_dir / "trademark" / "owner_sample.csv")
    filter_by_serial(targets["intl_class"], out_dir / "trademark" / "intl_class_sample.csv")
    filter_by_serial(targets["statement"], out_dir / "trademark" / "statement_sample.csv", args.max_statement_rows, True)
    return serials


def extract_platform(args, out_dir: Path, manifest: Dict) -> None:
    tdir = Path(args.temu_dir)
    names = ["temu_ip_policy", "Temu IP Policy", "intellectual_property_policy"]
    src = None
    for n in names:
        src = find_data_file(tdir, n)
        if src and src.suffix.lower() == ".pdf":
            break
    out = out_dir / "platform" / "temu_ip_policy.pdf"
    rows = 0
    if src and src.exists() and src.suffix.lower() == ".pdf":
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, out)
        rows = 1
    else:
        warn("Temu IP policy PDF not found.")
    info(f"platform/temu_ip_policy.pdf rows={rows}")
    manifest[str(out)] = {"rows": rows, "source": str(src or "")}


def extract_patent_claims(args, out_dir: Path, manifest: Dict, write_state: Dict[str, bool]) -> Set[str]:
    pdir = Path(args.patent_claims_dir)
    src_full = find_data_file(pdir, "patent_claims_fulltext")
    src_stats = find_data_file(pdir, "patent_claims_stats")
    src_doc = find_data_file(pdir, "patent_document_stats")
    for n, s in [("patent_claims_fulltext", src_full), ("patent_claims_stats", src_stats), ("patent_document_stats", src_doc)]:
        if not s:
            warn(f"Patent claims source missing: {n}")

    keyword_pat = re.compile("|".join(re.escape(k) for k in PRODUCT_KEYWORDS), flags=re.IGNORECASE)
    patent_ids: Set[str] = set()
    patent_id_field = None
    claim_text_field = None

    if src_full:
        for chunk in iter_csv_chunks(src_full, args.chunksize):
            if patent_id_field is None:
                patent_id_field, claim_text_field, claim_no_field, dependency_field, independent_field = detect_patent_fields(chunk.columns)
                if not patent_id_field or not claim_text_field:
                    warn(f"Cannot detect patent fields in {src_full}. Columns: {list(chunk.columns)}")
                    break
                info(f"Detected patent_id_field={patent_id_field}, claim_text_field={claim_text_field}")
                info(
                    "Optional claim fields: "
                    f"claim_no={claim_no_field}, dependencies={dependency_field}, independent_flag={independent_field}"
                )
            hit = chunk[chunk[claim_text_field].astype(str).str.contains(keyword_pat, na=False)]
            if hit.empty:
                continue
            for v in hit[patent_id_field].astype(str):
                patent_ids.add(normalize_patent_id(v))
                if len(patent_ids) >= args.max_patent_ids:
                    break
            if len(patent_ids) >= args.max_patent_ids:
                break

    full_out = out_dir / "patent_claims" / "patent_claims_fulltext_sample.csv"
    claim_rows = 0
    if src_full and patent_ids:
        for chunk in iter_csv_chunks(src_full, args.chunksize):
            if patent_id_field is None:
                patent_id_field, _, _, _, _ = detect_patent_fields(chunk.columns)
                if not patent_id_field:
                    warn(f"Cannot detect patent id in second pass. Columns: {list(chunk.columns)}")
                    break
            normalized = chunk[patent_id_field].astype(str).map(normalize_patent_id)
            filtered = chunk[normalized.isin(patent_ids)]
            if filtered.empty:
                continue
            if claim_rows + len(filtered) > args.max_claim_rows:
                filtered = filtered.head(args.max_claim_rows - claim_rows)
            append_csv(full_out, filtered, write_state)
            claim_rows += len(filtered)
            if claim_rows >= args.max_claim_rows:
                break

    if src_full and claim_rows == 0:
        warn("No keyword-based patent claims matched. Falling back to first N patent IDs.")
        fallback_ids: Set[str] = set()
        for chunk in iter_csv_chunks(src_full, args.chunksize):
            local_pid, _, _, _, _ = detect_patent_fields(chunk.columns)
            if not local_pid:
                warn(f"Cannot detect patent id for fallback. Columns: {list(chunk.columns)}")
                break
            for v in chunk[local_pid].astype(str):
                norm = normalize_patent_id(v)
                if norm:
                    fallback_ids.add(norm)
                if len(fallback_ids) >= args.fallback_patent_ids:
                    break
            if len(fallback_ids) >= args.fallback_patent_ids:
                break
        patent_ids = fallback_ids

        if patent_ids:
            for chunk in iter_csv_chunks(src_full, args.chunksize):
                local_pid, _, _, _, _ = detect_patent_fields(chunk.columns)
                if not local_pid:
                    warn(f"Cannot detect patent id in fallback second pass. Columns: {list(chunk.columns)}")
                    break
                normalized = chunk[local_pid].astype(str).map(normalize_patent_id)
                filtered = chunk[normalized.isin(patent_ids)]
                if filtered.empty:
                    continue
                if claim_rows + len(filtered) > args.max_claim_rows:
                    filtered = filtered.head(args.max_claim_rows - claim_rows)
                append_csv(full_out, filtered, write_state)
                claim_rows += len(filtered)
                if claim_rows >= args.max_claim_rows:
                    break

    info(f"patent_claims/patent_claims_fulltext_sample.csv rows={claim_rows}")
    manifest[str(full_out)] = {"rows": claim_rows, "source": str(src_full or "")}

    def filter_patent(src: Optional[Path], out: Path):
        rows = 0
        if src and patent_ids:
            local_pid = None
            for chunk in iter_csv_chunks(src, args.chunksize):
                if local_pid is None:
                    local_pid = pick_column(
                        chunk.columns,
                        ["pat_no", "patent_id", "patent", "patent_no", "patent_number", "doc_id", "document_id", "appl_id"],
                    )
                    if not local_pid:
                        warn(f"Cannot detect patent id for {src}. Columns: {list(chunk.columns)}")
                        break
                    info(f"Detected stats patent_id_field={local_pid} for {src.name}")
                normalized = chunk[local_pid].astype(str).map(normalize_patent_id)
                filtered = chunk[normalized.isin(patent_ids)]
                if filtered.empty:
                    continue
                append_csv(out, filtered, write_state)
                rows += len(filtered)
        info(f"{out.relative_to(out_dir)} rows={rows}")
        manifest[str(out)] = {"rows": rows, "source": str(src or "")}

    filter_patent(src_stats, out_dir / "patent_claims" / "patent_claims_stats_sample.csv")
    filter_patent(src_doc, out_dir / "patent_claims" / "patent_document_stats_sample.csv")
    return patent_ids


def extract_litigation(args, out_dir: Path, manifest: Dict, write_state: Dict[str, bool], patent_ids: Set[str]) -> None:
    ldir = Path(args.litigation_dir)
    src_cases = find_data_file(ldir, "cases")
    src_patents = find_data_file(ldir, "patents")
    src_names = find_data_file(ldir, "names")
    src_docs = find_data_file(ldir, "documents")

    for n, s in [("cases", src_cases), ("patents", src_patents), ("names", src_names), ("documents", src_docs)]:
        if not s:
            warn(f"Litigation source missing: {n}")

    patents_out = out_dir / "litigation" / "patents_sample.csv"
    case_ids: Set[str] = set()
    seen_keys: Set[Tuple[str, str]] = set()
    patents_rows = 0
    matched_rows = 0
    fallback_added = 0
    sample_case_preview: List[str] = []

    if src_patents:
        pcol = None
        ccol = None
        for chunk in iter_csv_chunks(src_patents, args.chunksize):
            if pcol is None:
                pcol = pick_column(chunk.columns, ["patent", "patent_id", "patent_no", "patent_number"])
                if not pcol:
                    warn(f"Cannot detect litigation patent columns: {list(chunk.columns)}")
                    break
                ccol = find_case_row_col(chunk)
            chunk = chunk.copy()
            chunk["normalized_patent"] = chunk[pcol].map(normalize_patent_id)
            chunk["normalized_case_row_id"] = normalize_case_row_id(chunk[ccol])
            chunk = chunk[(chunk["normalized_patent"] != "") & (chunk["normalized_case_row_id"] != "")]
            if chunk.empty:
                continue

            matched = chunk[chunk["normalized_patent"].isin(patent_ids)]
            if not matched.empty:
                keep_idx = []
                for idx, row in matched.iterrows():
                    key = (row["normalized_case_row_id"], row["normalized_patent"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    keep_idx.append(idx)
                    if patents_rows + len(keep_idx) >= args.max_litigation_patents:
                        break
                if keep_idx:
                    kept = matched.loc[keep_idx]
                    case_ids.update(kept["normalized_case_row_id"].tolist())
                    sample_case_preview.extend(kept["normalized_case_row_id"].head(10).tolist())
                    append_csv(patents_out, kept.drop(columns=["normalized_patent", "normalized_case_row_id"]), write_state)
                    patents_rows += len(kept)
                    matched_rows += len(kept)
                    if patents_rows >= args.max_litigation_patents:
                        break

            need_fallback = matched_rows < args.min_litigation_patents
            target_rows = min(args.fallback_litigation_patents, args.max_litigation_patents)
            if need_fallback and patents_rows < target_rows:
                fallback = chunk
                keep_idx = []
                for idx, row in fallback.iterrows():
                    key = (row["normalized_case_row_id"], row["normalized_patent"])
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    keep_idx.append(idx)
                    if patents_rows + len(keep_idx) >= target_rows:
                        break
                if keep_idx:
                    kept = fallback.loc[keep_idx]
                    case_ids.update(kept["normalized_case_row_id"].tolist())
                    sample_case_preview.extend(kept["normalized_case_row_id"].head(10).tolist())
                    append_csv(patents_out, kept.drop(columns=["normalized_patent", "normalized_case_row_id"]), write_state)
                    patents_rows += len(kept)
                    fallback_added += len(kept)
                    if patents_rows >= target_rows:
                        break

        if matched_rows < args.min_litigation_patents:
            warn(f"Only {matched_rows} litigation patent records matched claim sample patents. Falling back to additional litigation records.")

    info(f"litigation/patents_sample.csv rows={patents_rows}")
    manifest[str(patents_out)] = {"rows": patents_rows, "source": str(src_patents or "")}

    def filter_case_rows(src: Optional[Path], out: Path, max_rows: int, label: str) -> Tuple[int, Optional[str], List[str], List[str]]:
        rows = 0
        used_col = None
        first_chunk_preview: List[str] = []
        first_chunk_cols: List[str] = []
        if src and case_ids:
            for chunk in iter_csv_chunks(src, args.chunksize):
                if used_col is None:
                    used_col = find_case_row_col(chunk)
                    first_chunk_cols = list(chunk.columns)
                chunk = chunk.copy()
                chunk["normalized_case_row_id"] = normalize_case_row_id(chunk[used_col])
                if not first_chunk_preview:
                    first_chunk_preview = chunk["normalized_case_row_id"].head(10).tolist()
                filtered = chunk[chunk["normalized_case_row_id"].isin(case_ids)]
                if filtered.empty:
                    continue
                if rows + len(filtered) > max_rows:
                    filtered = filtered.head(max_rows - rows)
                append_csv(out, filtered.drop(columns=["normalized_case_row_id"]), write_state)
                rows += len(filtered)
                if rows >= max_rows:
                    break
        info(f"{out.relative_to(out_dir)} rows={rows}")
        manifest[str(out)] = {"rows": rows, "source": str(src or "")}
        return rows, used_col, first_chunk_preview, first_chunk_cols

    cases_rows, _, _, _ = filter_case_rows(src_cases, out_dir / "litigation" / "cases_sample.csv", args.max_litigation_cases, "cases")
    names_rows, names_case_col, names_preview, names_columns = filter_case_rows(src_names, out_dir / "litigation" / "names_sample.csv", args.max_litigation_names, "names")

    docs_out = out_dir / "litigation" / "documents_sample.csv"
    docs_rows = 0
    if src_docs and case_ids:
        ccol = None
        scol = None
        lcol = None
        dpat = re.compile("|".join(re.escape(k) for k in DOC_KEYWORDS), flags=re.IGNORECASE)
        try:
            for chunk in iter_csv_chunks(src_docs, args.chunksize):
                if ccol is None:
                    ccol = find_case_row_col(chunk)
                    scol = pick_column(chunk.columns, ["short_description"])
                    lcol = pick_column(chunk.columns, ["long_description"])
                chunk = chunk.copy()
                chunk["normalized_case_row_id"] = normalize_case_row_id(chunk[ccol])
                case_mask = chunk["normalized_case_row_id"].isin(case_ids)
                if not (scol or lcol):
                    text_mask = pd.Series([True] * len(chunk), index=chunk.index)
                else:
                    text = pd.Series([""] * len(chunk), index=chunk.index)
                    if scol:
                        text = text + " " + chunk[scol].astype(str)
                    if lcol:
                        text = text + " " + chunk[lcol].astype(str)
                    text_mask = text.str.contains(dpat, na=False)
                filtered = chunk[case_mask & text_mask]
                if filtered.empty:
                    continue
                if docs_rows + len(filtered) > args.max_documents:
                    filtered = filtered.head(args.max_documents - docs_rows)
                append_csv(docs_out, filtered.drop(columns=["normalized_case_row_id"]), write_state)
                docs_rows += len(filtered)
                if docs_rows >= args.max_documents:
                    break
        except Exception as e:
            warn(f"Failed to process documents sample: {e}")
    if docs_rows == 0:
        warn("No matching litigation documents were found. documents_sample.csv remains optional.")
    info(f"litigation/documents_sample.csv rows={docs_rows}")
    manifest[str(docs_out)] = {"rows": docs_rows, "source": str(src_docs or "")}

    if names_rows == 0:
        warn("names_sample.csv rows=0 debug info below")
        info(f"final patents_sample rows={patents_rows}")
        info(f"patents_sample normalized_case_row_id head={sample_case_preview[:10]}")
        info(f"names.csv normalized_case_row_id head(first chunk)={names_preview[:10]}")
        info(f"names.csv columns={names_columns}")
        info(f"names_case_col={names_case_col}")

    info("litigation summary:")
    info(f"matched_litigation_patents_from_claim_sample={matched_rows}")
    info(f"fallback_litigation_patents_added={fallback_added}")
    info(f"final_litigation_patents={patents_rows}")
    info(f"final_litigation_cases={cases_rows}")
    info(f"final_litigation_names={names_rows}")
    info(f"final_litigation_documents={docs_rows}")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Create lightweight sample data from local full datasets.")
    p.add_argument("--trademark_dir", default=r"C:\Users\dyy21\OneDrive\TJ\工作\资料\Rag\USPTO trademark")
    p.add_argument("--patent_claims_dir", default=r"C:\Users\dyy21\OneDrive\TJ\工作\资料\Rag\Patent Claims Research Dataset")
    p.add_argument("--litigation_dir", default=r"C:\Users\dyy21\OneDrive\TJ\工作\资料\Rag\Patent Litigation Docket Reports Data")
    p.add_argument("--temu_dir", default=r"C:\Users\dyy21\OneDrive\TJ\工作\资料\Rag\Temu")
    p.add_argument("--sample_dir", default="data/sample")
    p.add_argument("--max_trademark_cases", type=int, default=10000)
    p.add_argument("--max_statement_rows", type=int, default=50000)
    p.add_argument("--max_patent_ids", type=int, default=3000)
    p.add_argument("--max_claim_rows", type=int, default=50000)
    p.add_argument("--fallback_patent_ids", type=int, default=1000)
    p.add_argument("--max_litigation_patents", type=int, default=20000)
    p.add_argument("--min_litigation_patents", type=int, default=1000)
    p.add_argument("--fallback_litigation_patents", type=int, default=5000)
    p.add_argument("--max_litigation_cases", type=int, default=5000)
    p.add_argument("--max_litigation_names", type=int, default=30000)
    p.add_argument("--max_documents", type=int, default=2000)
    p.add_argument("--chunksize", type=int, default=200000)
    p.add_argument("--seed", type=int, default=42)
    return p


def main() -> None:
    args = build_parser().parse_args()
    random.seed(args.seed)

    sample_dir = Path(args.sample_dir)
    sample_dir.mkdir(parents=True, exist_ok=True)
    for sub in ["trademark", "platform", "patent_claims", "litigation"]:
        (sample_dir / sub).mkdir(parents=True, exist_ok=True)

    for path in sample_dir.rglob("*_sample.csv"):
        path.unlink(missing_ok=True)
    (sample_dir / "platform" / "temu_ip_policy.pdf").unlink(missing_ok=True)

    manifest_files: Dict[str, Dict[str, object]] = {}
    write_state: Dict[str, bool] = {}

    _ = extract_trademark(args, sample_dir, manifest_files, write_state)
    extract_platform(args, sample_dir, manifest_files)
    patent_ids = extract_patent_claims(args, sample_dir, manifest_files, write_state)
    extract_litigation(args, sample_dir, manifest_files, write_state, patent_ids)

    readme = sample_dir / "SAMPLE_README.md"
    readme.write_text(
        "# Sample Data Guide\n\n"
        "1. 本目录样本由 `scripts/make_sample_data_local.py` 从本地全量数据按关键词与关联键抽取得到。\n"
        "2. sample 仅用于 Demo、测试和 GitHub 展示。\n"
        "3. 全量数据应放在 `data/raw` 或通过本地路径读取。\n"
        "4. 不上传全量数据是因为体量大，不适合 GitHub 普通仓库。\n"
        "5. 真实运行时可基于全量数据构建 DuckDB、Chroma 和 BM25 索引。\n",
        encoding="utf-8",
    )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "parameters": vars(args),
        "files": [
            {
                "path": path,
                "rows": meta["rows"],
                "source": meta["source"],
                "sampled_at": datetime.now(timezone.utc).isoformat(),
            }
            for path, meta in sorted(manifest_files.items())
        ],
    }
    (sample_dir / "sample_manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    info("==== Summary ====")
    for f in manifest["files"]:
        print(f"{f['path']}: rows={f['rows']} source={f['source']}")


if __name__ == "__main__":
    main()
