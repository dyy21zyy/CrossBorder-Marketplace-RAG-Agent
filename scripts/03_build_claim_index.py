from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.load_patent_claims import iter_patent_claim_rows
from src.preprocessing.claim_group_builder import ClaimGroup, ClaimGroupBuilder
from src.retrieval.claim_retriever import ClaimRetriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build patent claim-group indexes")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--sample", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="max claim rows to consume")
    parser.add_argument("--batch_size", type=int, default=50000, help="row chunk size + embedding batch size")
    parser.add_argument("--resume", action="store_true", help="resume from existing claim_groups.jsonl")
    parser.add_argument("--force_rebuild", action="store_true", help="rebuild outputs/indexes from scratch")
    return parser.parse_args()


def _load_processed_patent_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    processed: set[str] = set()
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            patent_id = str(row.get("patent_id", "")).strip()
            if patent_id:
                processed.add(patent_id)
    return processed


def _load_claim_groups(path: Path) -> list[ClaimGroup]:
    groups: list[ClaimGroup] = []
    if not path.exists():
        return groups
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            row = json.loads(line)
            groups.append(ClaimGroup(**row))
    return groups


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(name)s | %(message)s")
    args = parse_args()
    prefer_raw = not args.sample
    output_path = Path("data/processed/claim_groups/claim_groups.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if args.force_rebuild and not args.resume:
        if output_path.exists():
            output_path.unlink()
        logging.info("force_rebuild=true: old claim_groups file removed")

    processed_patents = _load_processed_patent_ids(output_path) if args.resume else set()
    if processed_patents:
        logging.info("resume=true: skip already-processed patents: %d", len(processed_patents))

    rows = []
    for row in iter_patent_claim_rows(limit=args.limit, chunksize=args.batch_size, prefer_raw=prefer_raw):
        patent_id = str(row.get("patent_id", "")).strip()
        if args.resume and patent_id in processed_patents:
            continue
        rows.append(row)
        if len(rows) % 50000 == 0:
            logging.info("claim rows buffered: %d", len(rows))

    logging.info("claim rows to build: %d", len(rows))
    if rows:
        builder = ClaimGroupBuilder()
        claim_groups = builder.build(rows, context_path=str(output_path))
        write_mode = "a" if args.resume and output_path.exists() else "w"
        with output_path.open(write_mode, encoding="utf-8") as f:
            for group in claim_groups:
                f.write(json.dumps(group.__dict__, ensure_ascii=False) + "\n")
        logging.info("new claim groups written: %d", len(claim_groups))
    else:
        logging.info("no new claim rows to process")

    all_claim_groups = _load_claim_groups(output_path)
    logging.info("claim groups loaded for indexing: %d", len(all_claim_groups))

    retriever = ClaimRetriever()
    retriever.build_indexes(all_claim_groups, batch_size=args.batch_size, force_rebuild=args.force_rebuild)
    logging.info("Built claim groups total: %d", len(all_claim_groups))


if __name__ == "__main__":
    main()
