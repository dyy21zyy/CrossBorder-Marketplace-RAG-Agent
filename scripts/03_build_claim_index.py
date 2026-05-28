from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.ingestion.load_patent_claims import iter_patent_claim_rows
from src.preprocessing.claim_group_builder import ClaimGroupBuilder
from src.retrieval.claim_retriever import ClaimRetriever


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build patent claim-group indexes")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--sample", action="store_true")
    mode.add_argument("--full", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--batch_size", type=int, default=50000)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force_rebuild", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    prefer_raw = not args.sample
    output_path = Path("data/processed/claim_groups/claim_groups.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if output_path.exists() and args.force_rebuild and not args.resume:
        output_path.unlink()

    rows = list(iter_patent_claim_rows(limit=args.limit, chunksize=args.batch_size, prefer_raw=prefer_raw))
    builder = ClaimGroupBuilder()
    claim_groups = builder.build(rows, context_path=str(output_path))

    with output_path.open("w", encoding="utf-8") as f:
        for group in claim_groups:
            f.write(json.dumps(group.__dict__, ensure_ascii=False) + "\n")

    retriever = ClaimRetriever()
    retriever.build_indexes(claim_groups)
    print(f"Built claim groups: {len(claim_groups)}")


if __name__ == "__main__":
    main()
