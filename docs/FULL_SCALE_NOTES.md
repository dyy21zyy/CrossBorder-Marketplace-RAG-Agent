# FULL SCALE NOTES

## 1) 推荐硬件（本地全量构建）
- CPU: 8-16 cores
- RAM: 32GB（建议 64GB，特别是 patent claims 全量）
- Disk: NVMe SSD，至少 200GB 可用空间
- GPU: 非必须（当前 embedding 默认 CPU 可跑），有 GPU 可显著提速

## 2) Sample mode vs Full mode
- **Sample mode**：`data/sample/**`，用于本地开发、快速验收、CI。
- **Full mode**：`data/raw/**`，用于真实规模数据构建。
- Full mode 建议配合 `--limit`、`--batch_size`、`--resume` 控制风险与中断恢复。

## 3) 全量构建推荐顺序
1. `scripts/01_build_trademark_db.py`
2. `scripts/04_build_litigation_db.py`
3. `scripts/02_build_platform_index.py`
4. `scripts/03_build_claim_index.py`

说明：结构化 DuckDB 优先构建，便于先获得可查询基础能力，再追加向量索引。

## 4) Chroma 定位与替代
- 当前 **Chroma 是本地 MVP baseline**，适合单机验证与原型。
- 生产 full-scale 可替换为：Qdrant / Milvus / Elasticsearch / OpenSearch。
- 建议保持 Retriever 接口稳定（`ClaimRetriever` / hybrid retriever），底层向量库可插拔替换。

## 5) 为什么 litigation `documents.csv` 第一版不处理
- `documents.csv` 通常体量大、噪声高、字段异构且 OCR/清洗成本高。
- 第一版先聚焦 `cases/patents/names` 结构化闭环，优先保证可解释性与吞吐稳定。
- 后续可将 documents 作为二阶段召回源（按案件/专利先过滤再检索）。

## 6) 为什么 Structured RAG 更适合商标和诉讼表
- 商标、诉讼核心字段天然结构化（案号、状态、类别、日期、主体），SQL 过滤与 join 更准确。
- 全量向量化会引入无关语义噪声，且成本高、解释性弱。
- 结构化检索 + 局部语义检索（policy/claim）是更稳妥的工程折中。

## 7) 失败恢复与重建策略
- 默认不删除已有产物；中断后可直接 `--resume`。
- 仅 `--force_rebuild` 时删除旧索引/中间结果并全量重建。
- Claim 构建支持中间 `claim_groups.jsonl` 持久化与已处理专利跳过。

## 8) MVP 限制
- Chroma 仍为单机本地方案。
- 未覆盖 litigation `documents.csv` 语义管线。
- 目前尚未引入分布式任务编排（如 Airflow/Ray/Spark）。

## 9) 免责声明
本系统仅用于 **初步 IP 风险筛查**，不构成法律意见。
