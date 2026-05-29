# CrossBorder Marketplace RAG Agent

## 1. Project Overview

This project is a **RAG-LLM based cross-border e-commerce Listing intellectual property (IP) risk screening system**.

It helps sellers and operators perform preliminary checks on marketplace listing titles, descriptions, categories, and authorization status before publication. The system combines structured retrieval, hybrid text retrieval, optional reranking, rule-based risk judgment, and evidence-grounded LLM response generation.

> This project is designed for preliminary screening and workflow support. It does not provide legal conclusions or legal advice.

## 2. Supported Scenario

Current primary scenario:

- **Temu United States marketplace Listing IP risk screening**

The MVP focuses on U.S.-oriented IP signals and Temu platform policy evidence for listing review.

## 3. Data Sources

The current pipeline is built around the following data sources:

- **USPTO Trademark structured data**
- **USPTO Patent Claims Research Dataset**
- **Patent Litigation Docket Reports Data**
- **Temu IP Policy**
- **sample data / raw data** under the project `data/` directory

Sample data is intended for local development, smoke tests, and demos. Raw/full data is intended for larger-scale local or production indexing.

## 4. Why not vectorize everything

This project intentionally does **not** vectorize every source.

- **Trademark / litigation data is structured data**, so it is stored and queried with **DuckDB**. SQL filters, joins, exact fields, statuses, dates, classes, parties, and patent identifiers are more precise and explainable than full-vector search for these sources.
- **Platform policy / patent claims are long-text sources**, so they use **Chroma + BM25 + RRF**. Dense retrieval captures semantic similarity, BM25 preserves lexical matching, and Reciprocal Rank Fusion (RRF) combines the two recall channels.
- **Reranker is used for text evidence refinement**. After hybrid retrieval produces candidates, the BGE reranker can re-rank evidence snippets for better top-k precision.

This split keeps structured facts auditable while still supporting semantic retrieval over long policy and patent-claim text.

## 5. System Architecture

The current end-to-end architecture is:

```text
User Question / Listing
→ Query Parser
→ Query Rewriter
→ Trademark Structured RAG
→ Platform Policy Hybrid RAG
→ Patent Claim RAG
→ Litigation Structured RAG
→ Risk Judge
→ LLM Final Answer
→ Streamlit UI
```

Main implementation areas:

- Listing parsing and Chinese query parsing: `src/listing/`
- Query rewriting and retrieval: `src/retrieval/`
- Structured storage and vector indexing: `src/indexing/`
- Risk decision logic: `src/decision/`
- LLM agents and final answer generation: `src/agents/`
- Streamlit web UI: `src/webapp/app.py`
- Evaluation: `src/evaluation/` and `scripts/06_run_eval.py`

## 6. Chinese Input Support

The system supports Chinese user input with a cross-lingual workflow:

```text
中文输入 → 英文检索 query → 英文 evidence → 中文回答
```

In practice, Chinese listing questions are parsed and rewritten into English retrieval queries. Retrieval evidence remains grounded in English source material, while the final answer can be generated in Chinese for the user.

## 7. Reranker

The retrieval baseline and reranker-enhanced setup are both supported:

1. **Chroma + BM25 + RRF baseline**
2. **Chroma + BM25 + RRF + BGE Reranker**

RRF is used to fuse dense vector retrieval and BM25 sparse retrieval. The BGE reranker is a cross-encoder style evidence reranker used after first-stage retrieval. It may improve Precision@K and MRR, but it can increase latency and requires the local reranker model files.

## 8. LLM Configuration

Create a `.env` file or export environment variables before running LLM-backed flows.

```bash
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
MOCK_LLM=true/false
```

`MOCK_LLM=true` is useful for deterministic local demos, tests, and environments without a real model endpoint.

### DeepSeek-compatible example

```bash
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
MOCK_LLM=false
```

### Qwen-compatible example

```bash
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
MOCK_LLM=false
```

## 9. Installation

```bash
pip install -r requirements.txt
```

Optional virtual environment setup:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## 10. Model Download

The local MVP expects embedding and reranker models to be available under:

```text
models/bge-small-en-v1.5
models/bge-reranker-base
```

Do **not** upload model files to GitHub. The `models/` directory should stay ignored by Git because these files are large generated/local artifacts.

If downloading from Hugging Face is slow or blocked in your environment, configure an appropriate mirror before downloading, for example:

```bash
export HF_ENDPOINT=https://hf-mirror.com
```

## 11. Build Indexes

Build local sample indexes and databases:

```bash
python scripts/01_build_trademark_db.py --sample --force_rebuild
python scripts/02_build_platform_index.py
python scripts/03_build_claim_index.py --sample --limit 50000 --batch_size 2000 --force_rebuild
python scripts/04_build_litigation_db.py --sample --force_rebuild
```

The build outputs are local artifacts and should not be committed.

## 12. Run CLI Demo

### English listing demo

```bash
python scripts/05_run_demo.py --title "Phone case compatible with iPhone 15" --description "Magnetic transparent phone case for iPhone 15" --category "phone accessory" --platform "Temu" --has_authorization false --mock_llm true
```

### Patent and litigation demo

```bash
python scripts/05_run_demo.py --title "Foldable magnetic phone stand with ring holder" --description "Adjustable magnetic phone holder with foldable ring stand" --category "phone accessory" --platform "Temu" --has_authorization false --enable_patent_check true --enable_litigation_check true --use_reranker true --mock_llm true
```

## 13. Run Streamlit

Windows Command Prompt:

```bat
set PYTHONPATH=%CD%
python -m streamlit run src/webapp/app.py
```

macOS / Linux:

```bash
export PYTHONPATH=$PWD
python -m streamlit run src/webapp/app.py
```

Alternative helper script:

```bash
python scripts/07_run_webapp.py
```

## 14. Run Evaluation

Run all evaluation tasks:

```bash
python scripts/06_run_eval.py --all --mock_llm true
```

Compare retrieval with and without reranker:

```bash
python scripts/06_run_eval.py --retrieval --compare_reranker --mock_llm true
```

Run Chinese risk evaluation:

```bash
python scripts/06_run_eval.py --risk --zh --mock_llm true
```

Run Chinese response evaluation:

```bash
python scripts/06_run_eval.py --response --zh --mock_llm true
```

The evaluation suite covers retrieval quality, risk label behavior, and final response groundedness.

## 15. Current Limitations

- Sample data results are for demonstration only and do not represent full production coverage.
- Patent claim relevance may contain false positives because claim text can be broad and semantically similar to ordinary product descriptions.
- The system does not provide legal conclusions.
- EUIPO questions require a separate EU data source and are not covered by the current U.S.-focused MVP.
- Chroma is the local MVP vector store and is not intended as the final production-scale vector infrastructure.

## 16. Disclaimer

This system is for preliminary IP risk screening only and does not constitute legal advice.

中文：本系统仅用于知识产权风险初筛，不构成法律意见。

## 17. Future Work

- EUIPO FAQ RAG
- Amazon / AliExpress / TikTok Shop policy
- Qdrant / Milvus vector backend
- Knowledge Graph
- CLIP image logo detection
- More robust LLM judge
- Fine-tuning final answer generator
