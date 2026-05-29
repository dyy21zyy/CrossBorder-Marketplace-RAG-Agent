from __future__ import annotations

import os
import time
import traceback
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import get_settings
from src.listing.chinese_query_parser import parse_chinese_user_question
from src.schemas import ListingInput

INDEX_CHECKS = [
    {
        "name": "USPTO 商标 DuckDB",
        "path": Path("indexes/duckdb/trademark.duckdb"),
        "command": "python scripts/01_build_trademark_db.py --sample --force_rebuild",
    },
    {
        "name": "平台政策 Chroma 索引",
        "path": Path("indexes/chroma_platform"),
        "command": "python scripts/02_build_platform_index.py",
    },
    {
        "name": "专利权利要求 Chroma 索引",
        "path": Path("indexes/chroma_claims"),
        "command": "python scripts/03_build_claim_index.py --sample --limit 50000 --batch_size 2000 --force_rebuild",
    },
    {
        "name": "专利诉讼 DuckDB",
        "path": Path("indexes/duckdb/litigation.duckdb"),
        "command": "python scripts/04_build_litigation_db.py --sample --force_rebuild",
    },
    {
        "name": "平台政策 BM25 索引",
        "path": Path("indexes/bm25_platform"),
        "command": "python scripts/02_build_platform_index.py",
    },
    {
        "name": "专利权利要求 BM25 索引",
        "path": Path("indexes/bm25_claims"),
        "command": "python scripts/03_build_claim_index.py --sample --limit 50000 --batch_size 2000 --force_rebuild",
    },
]

DEFAULT_DISCLAIMER = "结果仅供知识产权风险初筛参考，不构成法律意见。"
LOCAL_RERANKER_MODEL_PATH = Path("models/bge-reranker-base")
ANSWER_LANGUAGE_OPTIONS = {"自动": "auto", "中文": "zh", "English": "en"}


def _risk_badge(level: str) -> str:
    normalized = (level or "unknown").lower()
    color = {
        "high": "🔴",
        "medium-high": "🟠",
        "medium": "🟡",
        "low": "🟢",
        "unknown": "⚪",
    }.get(normalized, "⚪")
    return f"{color} **{normalized.upper()}**"


def _bool_label(value: bool) -> str:
    return "✅ enabled / true" if value else "⚪ disabled / false"


def _configured_label(value: str) -> str:
    return "configured" if bool(value) else "missing"


def _path_exists(path: Path) -> bool:
    return path.exists()


def _collect_index_status() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in INDEX_CHECKS:
        path = item["path"]
        exists = _path_exists(path)
        rows.append(
            {
                "index": item["name"],
                "path": str(path),
                "status": "available" if exists else "missing",
                "build_command": "" if exists else item["command"],
            }
        )
    return rows


def _detect_missing(evidence_bundle: dict) -> list[str]:
    keys = {
        "trademark_evidence": "python scripts/01_build_trademark_db.py --sample --force_rebuild",
        "platform_policy_evidence": "python scripts/02_build_platform_index.py",
        "patent_claim_evidence": "python scripts/03_build_claim_index.py --sample --limit 50000 --batch_size 2000 --force_rebuild",
        "litigation_evidence": "python scripts/04_build_litigation_db.py --sample --force_rebuild",
    }
    missing: list[str] = []
    for ev_key, command in keys.items():
        if any(
            (x.evidence_type == "system" and "Please run" in x.snippet)
            for x in evidence_bundle.get(ev_key, [])
        ):
            missing.append(command)
    return missing


def _evidence_rows(evidence_bundle: dict) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in [
        "trademark_evidence",
        "platform_policy_evidence",
        "patent_claim_evidence",
        "litigation_evidence",
    ]:
        for item in evidence_bundle.get(key, []):
            metadata = item.metadata or {}
            rows.append(
                {
                    "source_type": item.evidence_type,
                    "source": item.source,
                    "score": round(float(item.score), 4),
                    "rrf_score": metadata.get("rrf_score"),
                    "reranker_score": metadata.get("reranker_score"),
                    "reranker_rank": metadata.get("reranker_rank"),
                    "retrieval_method": metadata.get("retrieval_method"),
                    "snippet": item.snippet,
                    "metadata": metadata,
                }
            )
    return rows


def run_pipeline(
    listing: ListingInput,
    enable_patent_check: bool,
    enable_litigation_check: bool,
    mock_llm: bool,
    use_reranker: bool,
    top_k: int,
    rerank_input_top_k: int | None,
    rerank_top_k: int | None,
    answer_language: str,
) -> tuple[dict, dict, list[dict], object, dict[str, Any]]:
    from src.agents.evidence_agent import EvidenceAgent
    from src.agents.final_answer_agent import FinalAnswerAgent
    from src.agents.listing_rewrite_agent import ListingRewriteAgent
    from src.agents.query_router_agent import QueryRouter
    from src.agents.risk_judge_agent import RiskJudgeAgent

    os.environ["MOCK_LLM"] = "true" if mock_llm else "false"
    get_settings.cache_clear()

    metrics: dict[str, Any] = {}
    started_at = time.perf_counter()
    query = (
        f"{listing.title} {listing.description} {listing.category} {listing.platform}"
    )

    routed_started_at = time.perf_counter()
    routed = QueryRouter().route(query)
    metrics["query_router_ms"] = round(
        (time.perf_counter() - routed_started_at) * 1000, 2
    )

    evidence_started_at = time.perf_counter()
    evidence_bundle = EvidenceAgent().collect(
        listing_input=listing,
        routed_intents=routed.get("intents", []),
        enable_patent_check=enable_patent_check,
        enable_litigation_check=enable_litigation_check,
        use_reranker=use_reranker,
        top_k=top_k,
        rerank_input_top_k=rerank_input_top_k,
        rerank_top_k=rerank_top_k,
        answer_language=answer_language,
    )
    metrics["evidence_collection_ms"] = round(
        (time.perf_counter() - evidence_started_at) * 1000, 2
    )

    risk_started_at = time.perf_counter()
    risk = RiskJudgeAgent().judge(evidence_bundle)
    metrics["risk_judge_ms"] = round((time.perf_counter() - risk_started_at) * 1000, 2)

    rewrite_started_at = time.perf_counter()
    rewrite = ListingRewriteAgent().rewrite(listing, risk, evidence_bundle)
    metrics["rewrite_ms"] = round((time.perf_counter() - rewrite_started_at) * 1000, 2)

    answer_started_at = time.perf_counter()
    answer = FinalAnswerAgent().generate(
        listing, evidence_bundle, risk, rewrite, answer_language=answer_language
    )
    metrics["final_answer_ms"] = round(
        (time.perf_counter() - answer_started_at) * 1000, 2
    )
    metrics["total_ms"] = round((time.perf_counter() - started_at) * 1000, 2)
    metrics["evidence_count"] = len(_evidence_rows(evidence_bundle))
    metrics["routed_intents"] = ", ".join(routed.get("intents", []))
    metrics["answer_language"] = evidence_bundle.get("answer_language", "")
    metrics["use_reranker"] = use_reranker
    metrics["top_k"] = top_k
    metrics["rerank_input_top_k"] = rerank_input_top_k or ""
    metrics["rerank_top_k"] = rerank_top_k or ""
    metrics["retrieval_query_en"] = evidence_bundle.get("retrieval_query_en", "")

    return evidence_bundle, risk, rewrite, answer, metrics


def _render_sidebar(
    st: Any,
    mock_llm: bool,
    enable_patent_check: bool,
    enable_litigation_check: bool,
    use_reranker: bool,
) -> None:
    settings = get_settings()
    using_real_llm = (not mock_llm) and bool(settings.openai_api_key)

    st.sidebar.header("系统状态")
    st.sidebar.markdown(f"- MOCK_LLM：`{str(mock_llm).lower()}`")
    st.sidebar.markdown(f"- 真实 LLM：{_bool_label(using_real_llm)}")
    st.sidebar.markdown(f"- OPENAI_MODEL：`{settings.openai_model or '未设置'}`")
    st.sidebar.markdown(f"- OPENAI_BASE_URL：`{settings.openai_base_url or '未设置'}`")
    st.sidebar.markdown(f"- API Key：**{_configured_label(settings.openai_api_key)}**")
    st.sidebar.divider()
    st.sidebar.markdown(f"- use_reranker：{_bool_label(use_reranker)}")
    st.sidebar.markdown(f"- enable_patent_check：{_bool_label(enable_patent_check)}")
    st.sidebar.markdown(
        f"- enable_litigation_check：{_bool_label(enable_litigation_check)}"
    )

    missing_count = sum(
        1 for row in _collect_index_status() if row["status"] == "missing"
    )
    st.sidebar.divider()
    st.sidebar.metric("缺失索引数量", missing_count)


def _render_screening_tab(st: Any, use_reranker_default: bool) -> None:
    st.markdown("#### 输入 Listing 信息")
    input_mode = st.radio(
        "输入模式",
        ["自然语言问题模式", "手动 Listing 表单模式"],
        index=0,
        horizontal=True,
    )

    parsed_query: dict[str, Any] | None = None
    if input_mode == "自然语言问题模式":
        question = st.text_area(
            "请输入你的问题 / 商品描述",
            "我想在 Temu 美国站上架一款适用于 iPhone 15 的透明磁吸手机壳，没有 Apple 授权，有知识产权风险吗？",
        )
        parsed_query = parse_chinese_user_question(question)
        st.markdown("#### 解析结果预览")
        preview_fields = [
            "title",
            "description",
            "category",
            "platform",
            "has_authorization",
            "enable_patent_check",
            "enable_litigation_check",
            "language",
        ]
        st.dataframe(
            pd.DataFrame(
                [
                    {"field": field, "value": parsed_query.get(field)}
                    for field in preview_fields
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )
        if parsed_query.get("market") == "EU":
            st.warning(
                "当前系统主要基于美国 USPTO 数据和 Temu 平台规则。欧盟 EUIPO 问题需要接入 EUIPO 数据源后才能准确回答。"
            )

        title = str(parsed_query.get("title", ""))
        description = str(parsed_query.get("description", ""))
        category = str(parsed_query.get("category", ""))
        platform = str(parsed_query.get("platform", ""))
        has_authorization = bool(parsed_query.get("has_authorization", False))
        patent_default = bool(parsed_query.get("enable_patent_check", False))
        litigation_default = bool(parsed_query.get("enable_litigation_check", False))
    else:
        title = st.text_input("商品标题", "Phone case compatible with iPhone 15")
        description = st.text_area(
            "商品描述", "Magnetic transparent phone case for iPhone 15"
        )
        c1, c2 = st.columns(2)
        category = c1.text_input("商品类目", "phone accessory")
        platform = c2.text_input("销售平台", "Temu")
        has_authorization = st.checkbox("已有品牌/专利授权", value=False)
        patent_default = False
        litigation_default = False

    st.markdown("#### 运行选项")
    mode_col, lang_col = st.columns(2)
    run_mode = mode_col.selectbox(
        "运行模式",
        ["快速模式", "精确模式", "自定义模式"],
        index=0,
        help="快速模式降低检索数量；精确模式启用 reranker 与更多证据；自定义模式允许手动勾选。",
    )
    answer_language_label = lang_col.selectbox(
        "回答语言", list(ANSWER_LANGUAGE_OPTIONS.keys()), index=0
    )
    answer_language = ANSWER_LANGUAGE_OPTIONS[answer_language_label]

    if run_mode == "快速模式":
        mode_use_reranker = False
        mode_top_k = 3
        mode_rerank_input_top_k = None
        mode_rerank_top_k = None
        patent_value = False
        litigation_value = False
    elif run_mode == "精确模式":
        mode_use_reranker = True
        mode_top_k = 5
        mode_rerank_input_top_k = 10
        mode_rerank_top_k = 5
        patent_value = patent_default
        litigation_value = litigation_default
    else:
        mode_use_reranker = use_reranker_default
        mode_top_k = 5
        mode_rerank_input_top_k = 10
        mode_rerank_top_k = 5
        patent_value = patent_default
        litigation_value = litigation_default

    opt1, opt2, opt3, opt4 = st.columns(4)
    mock_llm = opt1.checkbox(
        "使用 Mock LLM", value=True, help="开启后使用规则/模拟输出，便于本地演示。"
    )
    use_reranker = opt2.checkbox(
        "启用 Reranker 精排",
        value=mode_use_reranker,
        disabled=run_mode != "自定义模式",
    )
    enable_patent_check = opt3.checkbox(
        "启用专利 Claim 检索",
        value=patent_value,
        disabled=run_mode == "快速模式" or run_mode == "精确模式",
        key=f"patent_check_{input_mode}_{run_mode}_{patent_value}",
    )
    enable_litigation_check = opt4.checkbox(
        "启用诉讼历史查询",
        value=litigation_value,
        disabled=run_mode == "快速模式",
        key=f"litigation_check_{input_mode}_{run_mode}_{litigation_value}",
    )

    if run_mode == "自定义模式":
        custom1, custom2, custom3 = st.columns(3)
        top_k = custom1.number_input(
            "top_k", min_value=1, max_value=20, value=mode_top_k, step=1
        )
        rerank_input_top_k = custom2.number_input(
            "rerank_input_top_k",
            min_value=1,
            max_value=50,
            value=mode_rerank_input_top_k,
            step=1,
        )
        rerank_top_k = custom3.number_input(
            "rerank_top_k", min_value=1, max_value=20, value=mode_rerank_top_k, step=1
        )
    else:
        top_k = mode_top_k
        rerank_input_top_k = mode_rerank_input_top_k
        rerank_top_k = mode_rerank_top_k

    effective_use_reranker = use_reranker
    reranker_missing = use_reranker and not LOCAL_RERANKER_MODEL_PATH.exists()
    if reranker_missing:
        st.warning(
            "Reranker 模型未找到，请下载 models/bge-reranker-base 或关闭 reranker。已自动 fallback 到 no_reranker。"
        )
        effective_use_reranker = False

    st.caption(
        f"当前参数：mode={run_mode}, use_reranker={effective_use_reranker}, "
        f"top_k={top_k}, rerank_input_top_k={rerank_input_top_k or '-'}, "
        f"rerank_top_k={rerank_top_k or '-'}, answer_language={answer_language}"
    )

    submitted = st.button("开始风险筛查", type="primary")

    _render_sidebar(
        st,
        mock_llm,
        enable_patent_check,
        enable_litigation_check,
        effective_use_reranker,
    )

    if not submitted:
        st.info("填写 Listing 信息后，点击「开始风险筛查」运行演示。")
        return

    current_settings = get_settings()
    if not mock_llm and not current_settings.openai_api_key:
        st.error(
            "当前已关闭 mock_llm，但未配置 OPENAI_API_KEY。请在 .env 中配置 API Key，或重新勾选 mock_llm。"
        )
        return

    listing = ListingInput(
        title=title,
        description=description,
        category=category,
        platform=platform,
        has_authorization=has_authorization,
        original_question=(
            str(parsed_query.get("original_question", "")) if parsed_query else ""
        ),
    )

    try:
        with st.spinner("正在检索证据、判断风险并生成改写建议..."):
            evidence_bundle, risk, rewrite, answer, metrics = run_pipeline(
                listing,
                enable_patent_check,
                enable_litigation_check,
                mock_llm,
                effective_use_reranker,
                int(top_k),
                int(rerank_input_top_k) if rerank_input_top_k else None,
                int(rerank_top_k) if rerank_top_k else None,
                answer_language,
            )
    except Exception as exc:  # noqa: BLE001
        st.error(f"Pipeline 运行失败：{exc}")
        with st.expander("查看 traceback"):
            st.code(traceback.format_exc(), language="python")
        return

    st.subheader("0. Query Language Flow")
    st.markdown(
        f"**原始中文问题：** {evidence_bundle.get('original_question', listing.original_question or listing.title)}"
    )
    st.markdown(
        f"**英文检索 query：** `{evidence_bundle.get('retrieval_query_en', '')}`"
    )
    st.markdown(f"**回答语言：** `{evidence_bundle.get('answer_language', 'auto')}`")

    st.subheader("1. Overall Risk")
    st.markdown(_risk_badge(risk.get("overall_risk", "unknown")))

    st.subheader("2. Dimension Risks")
    dims = risk.get("dimension_risks", {})

    def _dim_level(key: str) -> str:
        value = dims.get(key, "unknown")
        return value.get("risk_level", "unknown") if isinstance(value, dict) else value

    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"**Trademark Risk**  \n{_risk_badge(_dim_level('trademark_risk'))}")
    c2.markdown(
        f"**Platform Policy Risk**  \n{_risk_badge(_dim_level('platform_policy_risk'))}"
    )
    c3.markdown(
        f"**Patent Claim Risk**  \n{_risk_badge(_dim_level('patent_claim_risk'))}"
    )
    c4.markdown(f"**Litigation Risk**  \n{_risk_badge(_dim_level('litigation_risk'))}")

    st.subheader("3. Evidence")
    rows = _evidence_rows(evidence_bundle)
    st.dataframe(
        pd.DataFrame(
            rows,
            columns=[
                "source_type",
                "source",
                "score",
                "rrf_score",
                "reranker_score",
                "reranker_rank",
                "retrieval_method",
                "snippet",
                "metadata",
            ],
        ),
        use_container_width=True,
        hide_index=True,
    )

    missing_commands = _detect_missing(evidence_bundle)
    if missing_commands:
        st.error("部分索引缺失，请先执行对应构建命令：")
        for command in dict.fromkeys(missing_commands):
            st.code(command, language="bash")

    st.subheader("4. Rewrite Suggestions")
    if rewrite:
        for idx, item in enumerate(rewrite, start=1):
            st.markdown(f"{idx}. **{item.get('title', '')}**")
            st.caption(item.get("reason", ""))
    else:
        st.info("暂无标题改写建议。")

    st.subheader("5. 中文最终回答 / Final Answer")
    st.write(answer.summary)

    st.subheader("6. Disclaimer")
    st.warning((answer.disclaimers or [DEFAULT_DISCLAIMER])[0])

    st.subheader("7. Performance Metrics")
    st.dataframe(pd.DataFrame([metrics]), use_container_width=True, hide_index=True)


def _render_evidence_tab(st: Any) -> None:
    st.markdown("### 检索证据")
    st.info(
        "在「风险筛查」页运行后，可在输出区域查看统一证据表。证据字段包括 source_type、source、score、rrf_score、reranker_score、reranker_rank、retrieval_method、snippet 和 metadata。"
    )
    st.markdown(
        "检索来源覆盖 USPTO 商标数据、平台 IP 政策、专利权利要求和专利诉讼摘要。"
    )


def _render_config_tab(st: Any) -> None:
    settings = get_settings()
    st.markdown("### 系统配置")
    config_rows = [
        {"item": "mock_llm", "value": settings.mock_llm},
        {"item": "use_reranker", "value": settings.use_reranker},
        {"item": "OPENAI_MODEL", "value": settings.openai_model or "未设置"},
        {
            "item": "OPENAI_BASE_URL",
            "value": _configured_label(settings.openai_base_url),
        },
        {"item": "OPENAI_API_KEY", "value": _configured_label(settings.openai_api_key)},
        {"item": "embedding_model_name", "value": settings.embedding_model_name},
        {"item": "reranker_model_name", "value": settings.reranker_model_name},
    ]
    st.dataframe(pd.DataFrame(config_rows), use_container_width=True, hide_index=True)

    st.markdown("### 索引状态检查")
    index_rows = _collect_index_status()
    st.dataframe(pd.DataFrame(index_rows), use_container_width=True, hide_index=True)

    missing = [row for row in index_rows if row["status"] == "missing"]
    if missing:
        st.warning("检测到缺失索引。请按需执行以下命令：")
        for command in dict.fromkeys(
            row["build_command"] for row in missing if row["build_command"]
        ):
            st.code(command, language="bash")
    else:
        st.success("所有检查项均已存在。")


def _render_eval_tab(st: Any) -> None:
    st.markdown("### 评估结果")
    st.info("可通过脚本运行离线评估，并将结果用于演示汇报。")
    st.code("python scripts/06_run_eval.py --mock_llm true", language="bash")


def _render_help_tab(st: Any) -> None:
    st.markdown("### 使用说明")
    st.markdown("""
1. 在「系统配置」页确认索引是否已构建，缺失时先执行页面提示的构建命令。
2. 在「风险筛查」页输入商品标题、描述、类目和平台。
3. 本地演示建议保持 `mock_llm` 开启；如需真实 LLM，请配置 `OPENAI_API_KEY`、`OPENAI_MODEL` 和可选的 `OPENAI_BASE_URL`。
4. 如需要专利或诉讼维度，请勾选 `patent check` / `litigation check` 并确保对应索引存在。
5. Windows 启动命令：
""")
    st.code(
        "set PYTHONPATH=%CD%\npython -m streamlit run src/webapp/app.py", language="bat"
    )
    st.warning(DEFAULT_DISCLAIMER)


def main() -> None:
    import streamlit as st

    st.set_page_config(
        page_title="跨境电商 Listing 知识产权风险筛查系统", layout="wide"
    )
    settings = get_settings()

    st.title("跨境电商 Listing 知识产权风险筛查系统")
    st.subheader("CrossBorder Marketplace RAG Agent")
    st.markdown(
        "本系统用于跨境电商商品上架前的知识产权风险初筛，结合 USPTO 商标数据、平台 IP 政策、专利权利要求和专利诉讼数据，输出风险提示、证据和标题改写建议。结果仅供初筛参考，不构成法律意见。"
    )

    tab_screening, tab_evidence, tab_config, tab_eval, tab_help = st.tabs(
        ["风险筛查", "检索证据", "系统配置", "评估结果", "使用说明"]
    )
    with tab_screening:
        _render_screening_tab(st, settings.use_reranker)
    with tab_evidence:
        _render_evidence_tab(st)
    with tab_config:
        _render_config_tab(st)
    with tab_eval:
        _render_eval_tab(st)
    with tab_help:
        _render_help_tab(st)


if __name__ == "__main__":
    main()
