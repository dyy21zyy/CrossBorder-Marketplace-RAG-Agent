# CrossBorder Marketplace RAG Agent

## Project Overview
A multi-source IP risk screening system for cross-border marketplace listings (US-oriented), combining structured retrieval, hybrid RAG, and optional LLM explanation.

## Business Problem
Sellers need fast **preliminary** checks for trademark/policy/patent/litigation signals before publishing listings.

## System Architecture
- Ingestion → Preprocessing → Indexing → Retrieval → Decision → Agents → Evaluation → UI
- Structured sources: DuckDB
- Unstructured/semi-structured: Chroma + BM25 + RRF

## Data Sources
- Trademark data (USPTO-like structured tables)
- Platform IP policy PDFs
- Patent claim datasets
- Litigation docket datasets

## Why not vectorize everything
- Structured fields should use SQL filters/joins (precision + explainability).
- Long text (policy/claims) benefits from embeddings.

## DuckDB Structured RAG
Used for:
- Trademark lookup and class/status evidence
- Litigation case summary by normalized patent id

## Hybrid RAG for policy and patent claims
- Vector retrieval + BM25 sparse retrieval
- RRF fusion for robust recall

## LLM role in the system
- Optional fallback for explanation/coordination
- Must be evidence-grounded
- Never outputs legal conclusion

## Sample Data Generation
```bash
python scripts/make_sample_data_local.py
```

## Installation
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Environment Variables
```bash
OPENAI_API_KEY=...
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
MOCK_LLM=true
```

## Build Trademark DB
```bash
python scripts/01_build_trademark_db.py --sample --force_rebuild
```

## Build Platform Policy Index
```bash
python scripts/02_build_platform_index.py
```

## Build Claim Index
```bash
python scripts/03_build_claim_index.py --sample --limit 50000
```

## Build Litigation DB
```bash
python scripts/04_build_litigation_db.py --sample --force_rebuild
```

## Run CLI Demo
```bash
python scripts/05_run_demo.py --title "Phone case compatible with iPhone 15" --description "Magnetic transparent case" --category "phone accessory" --platform "Temu" --has_authorization false --mock_llm true
```

## Run Streamlit Demo
```bash
python scripts/07_run_webapp.py
```

## Run Evaluation
```bash
python scripts/06_run_eval.py --mock_llm true
```

## Example Inputs and Outputs
- Input: title/description/category/platform/authorization
- Output: dimension risks (trademark/platform/patent/litigation), evidence snippets, rewrite suggestions, final disclaimer

## Limitations
- Sample data coverage is limited
- Litigation `documents.csv` not in core pipeline (MVP stage)
- Local vector store (Chroma) is single-node baseline

## Future Work
- Amazon IP Policy
- AliExpress / TikTok Shop policy
- Reranker
- Low-confidence second retrieval
- Litigation documents stage classification
- Knowledge Graph: Brand–Trademark–Patent–Litigation
- NetworkX / Neo4j
- Louvain community detection
- Image Logo detection
- CLIP image retrieval
- Qdrant / Milvus replacement for Chroma

## Disclaimer
For **preliminary IP risk screening only**. Not legal advice.
