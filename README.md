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
