# Full-scale Notes

## 1. Project Positioning

This repository implements a **RAG-LLM based cross-border e-commerce Listing intellectual property risk screening system**.

The current primary scenario is **Temu U.S. marketplace Listing IP risk screening**. The pipeline is optimized for preliminary screening of trademark, platform-policy, patent-claim, and litigation signals before a listing is published.

## 2. Data Source Strategy

The project uses different retrieval/indexing strategies for different data types:

- **USPTO Trademark structured data**: structured tables queried with DuckDB.
- **Patent Litigation Docket Reports Data**: structured case, patent, and party data queried with DuckDB.
- **Temu IP Policy**: long-form policy text indexed with Chroma + BM25 + RRF.
- **USPTO Patent Claims Research Dataset**: long-form patent claim text indexed with Chroma + BM25 + RRF.
- **sample data / raw data**: sample data is for local demos and tests; raw data is for full-scale builds.

## 3. Why not vectorize everything

Full vectorization is not the best engineering choice for this project.

- **Trademark and litigation records are structured evidence**. They contain fields such as marks, owners, classes, registration status, patent identifiers, case metadata, parties, and dates. DuckDB queries preserve precision, filtering, joins, and auditability.
- **Platform policy and patent claims are long-text evidence**. Hybrid retrieval with Chroma + BM25 + RRF gives better recall across semantic and lexical matching.
- **Reranker is a second-stage text evidence sorter**. It is applied after hybrid retrieval to refine evidence order, not to replace structured SQL retrieval.

This architecture keeps exact structured facts separate from semantic long-text retrieval.

## 4. Architecture Flow

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

The flow supports English and Chinese user inputs. For Chinese inputs, the intended workflow is:

```text
中文输入 → 英文检索 query → 英文 evidence → 中文回答
```

## 5. Recommended Hardware for Local Full Builds

- CPU: 8-16 cores
- RAM: 32 GB minimum; 64 GB recommended for larger patent-claim builds
- Disk: NVMe SSD with at least 200 GB free space for raw data and indexes
- GPU: optional; useful for faster embedding/reranker execution but not required for the MVP

## 6. Sample Mode vs Full Mode

- **Sample mode**: uses `data/sample/**`; intended for local development, fast acceptance checks, smoke tests, and demos.
- **Full mode**: uses `data/raw/**`; intended for real-scale indexing and larger experiments.

Full mode should be run with explicit `--limit`, `--batch_size`, and resume/rebuild settings to reduce operational risk.

## 7. Full-scale Build Order

Recommended local build order:

```bash
python scripts/01_build_trademark_db.py --sample --force_rebuild
python scripts/02_build_platform_index.py
python scripts/03_build_claim_index.py --sample --limit 50000 --batch_size 2000 --force_rebuild
python scripts/04_build_litigation_db.py --sample --force_rebuild
```

Structured DuckDB databases can be built first to establish reliable trademark and litigation lookup. Long-text vector/BM25 indexes can then be built for policy and patent-claim retrieval.

## 8. Reranker Configuration

Two retrieval configurations are supported for comparison:

1. **Chroma + BM25 + RRF baseline**
2. **Chroma + BM25 + RRF + BGE Reranker**

The expected local model paths are:

```text
models/bge-small-en-v1.5
models/bge-reranker-base
```

Do not commit these model directories to GitHub. They are large local artifacts and should remain ignored by Git.

## 9. LLM Endpoint Configuration

The LLM client follows OpenAI-compatible environment variables:

```bash
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
MOCK_LLM=true/false
```

DeepSeek-compatible example:

```bash
OPENAI_BASE_URL=https://api.deepseek.com/v1
OPENAI_MODEL=deepseek-chat
```

Qwen-compatible example:

```bash
OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
OPENAI_MODEL=qwen-plus
```

Use `MOCK_LLM=true` for deterministic demos, local smoke tests, and environments without external model access.

## 10. Chroma Positioning and Production Alternatives

Chroma is currently the **local MVP vector store**. It is suitable for single-node prototyping, demos, and small local experiments.

For production or large-scale retrieval, consider replacing it with:

- Qdrant
- Milvus
- Elasticsearch
- OpenSearch

Retriever interfaces should stay stable so the underlying vector backend can be replaced without changing the business logic.

## 11. Litigation Documents Scope

The first version focuses on structured litigation tables rather than full semantic processing of `documents.csv`.

Reasons:

- Litigation documents are often large, noisy, and heterogeneous.
- OCR and document-cleaning quality can dominate retrieval quality.
- Structured case/patent/name data provides a more explainable MVP retrieval loop.

A later version can add litigation document retrieval as a second-stage source after filtering by case, patent, or party.

## 12. Failure Recovery and Rebuild Strategy

- Existing artifacts are generally preserved unless `--force_rebuild` is used.
- Use `--force_rebuild` when you need to delete old outputs and rebuild from scratch.
- Patent-claim indexing should be run with controlled batch sizes for large datasets.
- Generated databases, vector indexes, BM25 artifacts, and local models should not be committed.

## 13. Evaluation Commands

```bash
python scripts/06_run_eval.py --all --mock_llm true
python scripts/06_run_eval.py --retrieval --compare_reranker --mock_llm true
python scripts/06_run_eval.py --risk --zh --mock_llm true
python scripts/06_run_eval.py --response --zh --mock_llm true
```

Evaluation currently covers retrieval metrics, risk-label behavior, Chinese scenarios, response groundedness, citation coverage, and disclaimer behavior.

## 14. Current Limitations

- Sample data results are for demonstration only.
- Patent claim relevance may contain false positives.
- The system does not provide legal conclusions.
- EUIPO questions require a separate EU data source.
- Chroma is a local MVP vector store.
- Litigation `documents.csv` semantic retrieval is not part of the first structured-litigation pipeline.

## 15. Disclaimer

This system is for preliminary IP risk screening only and does not constitute legal advice.

中文：本系统仅用于知识产权风险初筛，不构成法律意见。

## 16. Future Work

- EUIPO FAQ RAG
- Amazon / AliExpress / TikTok Shop policy
- Qdrant / Milvus
- Knowledge Graph
- CLIP image logo detection
- More robust LLM judge
- Fine-tuning final answer generator
