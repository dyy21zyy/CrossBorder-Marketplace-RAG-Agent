# CrossBorder Marketplace RAG Agent

## 项目背景
本项目旨在搭建一个“基于 RAG-LLM 的美国市场跨境电商 Listing 侵权风险检索系统”框架。
用户输入商品标题、描述、类目、平台与授权状态后，系统输出以下风险与建议：
- 商标风险（Trademark Risk）
- 平台 IP 规则风险（Platform Policy/IP Risk）
- 专利 Claim 相关风险（Patent Claim Risk）
- 专利诉讼风险（Litigation Risk）
- Listing 修改建议（Listing Rewrite Suggestions）

当前阶段仅完成工程骨架与最小可导入结构，不包含复杂业务逻辑。

## 数据源
计划接入的数据源分为四类：
1. 商标数据（USPTO 等）
2. 平台政策与 IP 规则（Amazon/eBay/Walmart 等）
3. 专利 Claim 数据（USPTO/Google Patents 或企业自有库）
4. 专利诉讼数据（PACER/CourtListener/第三方聚合）

> 说明：本仓库目前仅提供目录约定与占位脚本，具体采集与清洗流程后续完善。

## 技术路线
- **Ingestion**：多源数据加载与标准化
- **Preprocessing**：分块、清洗、Claim 分组、结构化映射
- **Indexing**：DuckDB + Chroma + BM25 混合索引
- **Retrieval**：按风险类型检索并做 RRF 融合
- **Decision**：规则引擎 + LLM 风险裁决
- **Agents**：查询路由、证据汇总、风险判断、重写建议、最终答复
- **Evaluation**：检索与风险评估集、离线报告
- **WebApp**：基础 Streamlit 展示层

## 目录结构
项目目录采用模块化分层，详见 `src/`、`configs/`、`data/`、`indexes/`、`scripts/` 与 `tests/`。

## 运行顺序（建议）
1. 创建并激活 Python 虚拟环境
2. 安装依赖：`pip install -r requirements.txt`
3. 复制环境变量：`cp .env.example .env`
4. 准备样例数据：`python scripts/make_sample_data_local.py`
5. 依次执行构建脚本：
   - `python scripts/01_build_trademark_db.py`
   - `python scripts/02_build_platform_index.py`
   - `python scripts/03_build_claim_index.py`
   - `python scripts/04_build_litigation_db.py`
6. 运行 Demo：`python scripts/05_run_demo.py`
7. 运行评估：`python scripts/06_run_eval.py`
8. 启动 Web 应用：`python scripts/07_run_webapp.py`

## 免责声明
- 本项目仅用于技术研究与工程演示，不构成法律意见。
- 侵权风险判断结果仅供参考，实际合规结论应由专业律师或合规团队复核。
- 数据源可能存在时效性与覆盖范围限制，需结合最新官方信息使用。

## 配置方式
项目使用 `configs/default.yaml` + `.env` 的双层配置：
- `configs/default.yaml`：存放工程默认路径与检索参数（如 `top_k`、`rerank_top_k`）。
- `.env`：存放敏感或环境相关参数（如 OpenAI Key/Model），不建议提交到版本库。
- 运行时通过 `src/config.py` 中的 `get_settings()` 统一加载配置。

## `.env` 使用方式
可在项目根目录创建 `.env`（示例）：

```bash
OPENAI_API_KEY=your_api_key
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_MODEL=gpt-4.1-mini
MOCK_LLM=true
```

说明：
- `MOCK_LLM` 支持 `true/false`、`1/0`、`yes/no` 等布尔写法。
- 当 `MOCK_LLM=true` 时，可用于本地调试时跳过真实 LLM 调用流程（本项目当前任务不包含调用 LLM）。

## sample 数据和 raw 数据区别
- `data/sample/`：轻量样例数据，用于本地开发、联调与 CI 快速验证。
- `data/raw/`：原始全量或准全量数据，用于真实构建索引与效果评估，体量通常较大且来源多样。

建议开发流程：先用 `sample` 跑通端到端，再切换 `raw` 做效果验证与性能测试。

## 为什么 full-scale 数据不上传 GitHub
- **体积限制**：GitHub 对大文件与仓库体积不友好，影响 clone/pull 速度。
- **版权与许可**：部分外部数据源存在使用条款，不能二次分发。
- **合规与隐私**：某些数据可能含敏感字段，需在受控环境使用。
- **可维护性**：大规模数据频繁更新，建议通过离线数据管道或对象存储管理，而非直接随代码版本化。

## Creating Sample Data from Local Full Datasets
使用以下命令从本地全量数据抽取可上传到 GitHub 的轻量 sample 数据：

```bash
python scripts/make_sample_data_local.py
```

Patent Claims Research Dataset 的实际字段如下（脚本已按这些字段优先识别）：

- `pat_no`：专利号
- `claim_no`：权利要求编号
- `claim_txt`：权利要求文本
- `dependencies`：从属关系
- `ind_flg`：是否独立权利要求
- `appl_id`：申请编号

Litigation sample 生成逻辑（Patent Litigation Docket Reports Data）：

- 优先保留可与 Patent Claims sample 中 patent_id 匹配的诉讼专利记录。
- 若匹配行数过少（默认小于 `--min_litigation_patents 1000`），脚本会从 litigation/patents 中补充真实记录（默认补齐到 `--fallback_litigation_patents 5000`，且不超过 `--max_litigation_patents`），以保证 demo 可运行。
- `cases.csv` / `patents.csv` / `names.csv` / `documents.csv` 的案件连接键可能是 `case_row_id` 或 `case_row`（也兼容 `case_id` 等），脚本会自动识别并规范化后关联。
- `documents_sample.csv` 是可选样本；第一版系统主要使用 `cases`、`patents`、`names`。

Windows 显式传参示例：

```bash
python scripts/make_sample_data_local.py ^
  --trademark_dir "C:\Users\dyy21\OneDrive\TJ\工作\资料\Rag\USPTO trademark" ^
  --patent_claims_dir "C:\Users\dyy21\OneDrive\TJ\工作\资料\Rag\Patent Claims Research Dataset" ^
  --litigation_dir "C:\Users\dyy21\OneDrive\TJ\工作\资料\Rag\Patent Litigation Docket Reports Data" ^
  --temu_dir "C:\Users\dyy21\OneDrive\TJ\工作\资料\Rag\Temu" ^
  --sample_dir "data/sample"
```

## Trademark Structured RAG（USPTO）
USPTO Trademark 数据是天然结构化表（案件、权利人、尼斯分类、声明等），适合走 **DuckDB Structured RAG** 路线：
- 先将 CSV 原表导入 DuckDB（`raw_*`）；
- 再构建轻量检索表（`trademark_case/owner/class/statement`）；
- 检索阶段按字段过滤、关联与聚合，而非把全量记录转成长文本。

### 为什么 USPTO Trademark 不直接向量化
- 结构字段可精确过滤（如 `serial_no`、`statement_type_cd`、`intl_class_cd`），向量检索会引入不必要噪声。
- 大规模 Trademark 全量文本向量化成本高、更新慢，不利于可控检索。
- 合规风控场景强调可追溯和可解释，Structured RAG 更容易还原证据路径。

### 构建命令
```bash
python scripts/01_build_trademark_db.py --sample --force_rebuild
```

脚本会自动：
1. 初始化 `indexes/duckdb/trademark.duckdb`；
2. 导入 Trademark 原始 CSV（优先 `data/raw/trademark`，不存在时回退 `data/sample/trademark`）；
3. 构建轻量检索表并创建索引；
4. 打印各表行数。

## Trademark 风险筛查 Demo（Structured RAG + Rule Engine）
> 当前阶段仅执行结构化检索与规则判断，不调用 LLM，不输出法律结论。

先确保 DuckDB 已构建：

```bash
python scripts/01_build_trademark_db.py --sample --force_rebuild
```

再运行 Demo：

```bash
python scripts/05_run_demo.py --title "Phone case compatible with iPhone 15" --description "Magnetic transparent case for iPhone 15" --category "phone accessory" --platform "Temu" --has_authorization false
```

若缺少数据库，Demo 会提示先执行上述构建命令。

## Temu IP Policy Hybrid RAG（非结构化/半结构化）
Temu IP Policy 属于规则文档，不是关系表结构，因此不适合走 Trademark 的 DuckDB Structured RAG。
这里采用 **Hybrid RAG**：
- 按页面读取 PDF（优先 `data/raw/platform/temu_ip_policy.pdf`，不存在则 fallback `data/sample/platform/temu_ip_policy.pdf`）；
- 做 **section-aware chunking**（按 trademark/copyright/patent/report infringement/counter notice/enforcement/repeat infringement/general 分段）；
- 同时构建：
  - Chroma 向量索引（语义召回）
  - BM25 关键词索引（精确词召回）
- 查询时用 **RRF** 融合两个排序结果，提升召回稳定性与可解释性。

### 构建 Temu Policy 索引
```bash
python scripts/02_build_platform_index.py
```

构建产物：
- `data/processed/platform/platform_chunks.jsonl`
- `indexes/chroma_platform/`
- `indexes/bm25_platform/bm25_platform.pkl`

### Demo 中自动触发平台政策检索
在 `scripts/05_run_demo.py` 中，当商标风险被判定为 `high/medium` 时，系统会自动发起 Temu Policy 检索：
- query: `Temu intellectual property trademark infringement report enforcement`
- 输出 `platform_policy_evidence`，并显示 `source / section / page / chunk_text`。

## Patent Claim-level RAG（Claim Grouping First）
专利文本**不能按普通 token 随机切块**。侵权风险初筛的核心证据单位是 Claims，尤其是 Independent Claim。Dependent Claim 必须与其引用的 Independent Claim 合并为 claim group，再进入检索。

### Claim Group 规则
- 按 `pat_no/patent_id` 分组。
- `ind_flg` 为 `1/true/y`，或依赖关系为空时，优先判定为独立权利要求。
- 从属权利要求会解析 `dependencies` 和文本中的 `claim 1`、`claims 1-3` 等引用。
- 若依赖关系无法解析，则回退合并到最近的前序独立权利要求。
- 若某专利不存在可识别独立权利要求，则每条 claim 独立成组作为 fallback。

### 索引与检索
- 构建脚本：`python scripts/03_build_claim_index.py --sample --limit 50000`
- 支持 `--sample/--full/--limit/--batch_size/--resume/--force_rebuild`
- 当前 MVP 使用本地 Chroma + BM25 + RRF；后续可平滑替换为 Qdrant/Milvus。

### 合规声明
本模块仅用于专利风险初筛。系统输出为“发现相关权利要求，需要人工核验”，不构成专利侵权认定或法律意见。

## Patent Litigation Structured RAG（DuckDB）
Patent Litigation Docket Reports Data 属于案件结构化数据，**不作为普通文本 chunk 向量化**。当前实现采用 DuckDB Structured RAG 路线：
- `patent -> case_row_id -> cases -> names` 进行结构化关联；
- 优先读取 `data/raw/litigation/`，不存在时 fallback 到 `data/sample/litigation/`；
- 第一版仅接入 `cases(.csv/_sample.csv)`、`patents(...)`、`names(...)`；
- `documents.csv / attorneys.csv / pacer_cases.csv` 暂作为 future work，不进入核心流程。

### 连接键自动识别
不同源文件的案件键可能不同，系统会自动识别以下字段作为案件连接键：
- `case_row_id`
- `case_row`
- `case_id`
- `caseid`
- `case_rowid`

并统一规范化后用于关联，避免把 `party_row_count` 误当作案件键。

### 构建命令
```bash
python scripts/04_build_litigation_db.py --sample --force_rebuild
```

支持参数：
- `--sample`：强制使用 sample 数据；
- `--full`：强制使用 raw 数据；
- `--force_rebuild`：重建原始表与衍生表。

## LLM + RAG Pipeline
本项目采用“检索优先、LLM 兜底”的多源流程：
- DuckDB / Chroma / BM25 / RRF 负责证据检索与召回；
- Rule Engine 负责稳定初步风险判断；
- LLM 仅用于复杂路由兜底、冲突判断和最终解释生成；
- LLM 不直接读取原始 CSV；
- LLM 不能脱离 evidence 做法律结论。

## Final Answer Agent
`FinalAnswerAgent` 基于 `EvidenceBundle + RiskResult + ListingRewrite suggestions` 输出结构化最终解释。
核心约束：
- 只可基于 evidence；
- 证据不足必须输出 unknown / not enough evidence；
- 不输出“构成侵权”或“完全安全”；
- 永远附带免责声明：This system is for preliminary IP risk screening only and does not constitute legal advice.

## Listing Rewrite Agent
`ListingRewriteAgent` 基于风险与证据给出 2-3 条更稳健标题建议，并附 reason：
- 删除 `style / inspired by / look alike / fake / replica / dupe`；
- 弱化 `compatible with`；
- 无授权时降低品牌词在标题核心位置；
- 避免 `official / authorized / genuine / authentic` 等可能误导词。

## Full Pipeline Demo
```bash
python scripts/05_run_demo.py \
  --title "Phone case compatible with iPhone 15" \
  --description "Magnetic transparent case for iPhone 15" \
  --category "phone accessory" \
  --platform "Temu" \
  --has_authorization false \
  --enable_patent_check false \
  --enable_litigation_check false \
  --mock_llm true
```

## `.env` 示例
```bash
MOCK_LLM=true
OPENAI_API_KEY=
OPENAI_BASE_URL=
OPENAI_MODEL=
```

兼容 API 示例：
- OpenAI Compatible: `OPENAI_BASE_URL=https://api.openai.com/v1`
- DeepSeek Compatible: `OPENAI_BASE_URL=https://api.deepseek.com/v1`
- Qwen Compatible: `OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1`

即使没有 API Key，也可使用 `MOCK_LLM=true` 跑通全流程。
