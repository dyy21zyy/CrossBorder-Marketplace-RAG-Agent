from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import get_settings
from src.ingestion.load_platform_policy import load_platform_policy_pages, resolve_platform_policy_path
from src.indexing.bm25_index import build_bm25_index
from src.indexing.chroma_store import build_chroma_index
from src.preprocessing.platform_chunker import chunk_platform_policy


def main() -> None:
    settings = get_settings()
    pdf_path = resolve_platform_policy_path()
    pages = load_platform_policy_pages(pdf_path)
    chunks = chunk_platform_policy(pages)

    out_path = Path("data/processed/platform/platform_chunks.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(json.dumps(chunk, ensure_ascii=False) + "\n")

    build_chroma_index(chunks, settings.chroma_platform_dir, "temu_ip_policy")
    build_bm25_index(chunks, settings.bm25_platform_path)

    print(f"Loaded policy PDF: {pdf_path}")
    print(f"Built platform chunks: {len(chunks)}")
    print(f"Saved chunks: {out_path}")


if __name__ == "__main__":
    main()
