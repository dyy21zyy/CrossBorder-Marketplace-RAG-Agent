# FULL SCALE NOTES

## 1) Sample mode vs Full mode
- **Sample mode** uses `data/sample/**` for local development, CI, and quick smoke tests.
- **Full mode** uses `data/raw/**` (or your production data lake) for realistic coverage and recall.

## 2) Why full CSV is not uploaded to GitHub
- Repository size and clone speed constraints.
- License / redistribution limits for third-party datasets.
- Compliance/privacy constraints.
- High update frequency makes Git-based versioning inefficient for large data.

## 3) Full-scale supported modules
- Trademark DuckDB (structured retrieval)
- Litigation DuckDB (structured retrieval)
- Platform Policy RAG (vector + BM25 hybrid)
- Patent Claim RAG (claim-group level vector + BM25 hybrid)

## 4) MVP modules
- Local Chroma vector store (single-node local baseline)
- `documents.csv` in litigation is currently **not** in the main pipeline

## 5) Recommendations for large-scale deployment
- Use DuckDB (or warehouse SQL engines) for structured tables.
- Replace local Chroma with Qdrant / Milvus / Elasticsearch for scale-out retrieval.
- Run claim embedding in batch jobs.
- Build indexing with resumable checkpoints (`--resume`).

## 6) Why not vectorize all data
- Structured fields are better queried with SQL filters and joins.
- Long-form semantic matching benefits from embeddings; not every field does.

## 7) Disclaimer
This system is for **preliminary IP risk screening only** and does **not** constitute legal advice.
