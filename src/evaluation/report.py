from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def save_json(path: str, data: dict[str, Any]):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def build_markdown_report(
    retrieval_result: dict[str, Any] | None,
    risk_result: dict[str, Any] | None,
    response_result: dict[str, Any] | None,
    out_path="reports/evaluation_report.md",
) -> str:
    lines = [
        "# Evaluation Report",
        "",
        "Results are based on sample data and are intended for demonstration.",
        "",
        "## 1. Retrieval Evaluation",
        "",
        "### Context Relevance Metrics",
        "| module | Precision@5 | Recall@5 | F1@5 | MRR | MAP | Context Relevance | Avg Latency |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    if retrieval_result:
        zero_recall_modules = []
        for m in retrieval_result.get("no_reranker", {}).get("by_module", []):
            lines.append(
                f"| {m['module']} | {m['precision_at_k']:.3f} | {m['recall_at_k']:.3f} | {m['f1_at_k']:.3f} | {m['mrr']:.3f} | {m['map']:.3f} | {m['context_relevance']:.3f} | {m['avg_latency_sec']:.3f} |"
            )
            if m.get("recall_at_k", 0) == 0:
                zero_recall_modules.append(m["module"])
        if zero_recall_modules:
            lines += ["", "### Retrieval Diagnostics"]
            for module in zero_recall_modules:
                lines.append(
                    f"- {module}: 可能是 eval labels 与 evidence 字段不匹配，或检索模块未返回可搜索文本。"
                )
        if retrieval_result.get("reranker_ablation"):
            lines += [
                "",
                "### Reranker Ablation",
                "| module | Recall@5 No Reranker | Recall@5 With Reranker | Δ Recall | Δ MRR | Δ Latency |",
                "|---|---:|---:|---:|---:|---:|",
            ]
            for d in retrieval_result["reranker_ablation"]:
                lines.append(
                    f"| {d['module']} | {d.get('recall_at_5_no_reranker',0):.3f} | {d.get('recall_at_5_with_reranker',0):.3f} | {d.get('recall_at_5_delta',0):.3f} | {d.get('mrr_delta',0):.3f} | {d.get('latency_delta',0):.3f} |"
                )
            lines += ["", "#### Reranker Evidence Preview"]
            for d in retrieval_result["reranker_ablation"]:
                lines.append(
                    f"- **{d['module']} no_reranker top**: {d.get('no_reranker_top_evidence_preview','')}"
                )
                lines.append(
                    f"- **{d['module']} with_reranker top**: {d.get('with_reranker_top_evidence_preview','')}"
                )
                if d.get("with_reranker_top_evidence_scores"):
                    lines.append(
                        f"  - with_reranker scores: `{json.dumps(d.get('with_reranker_top_evidence_scores'), ensure_ascii=False)}`"
                    )
                for warning in d.get("warnings", []):
                    lines.append(f"  - Warning: {warning}")

    lines += [
        "",
        "## 2. Risk Evaluation",
        "| risk type | Accuracy | High-risk Recall | Unknown Handling | False Positive Rate | False Negative Rate |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    if risk_result:
        m = risk_result.get("no_reranker", risk_result).get("metrics", {})
        for d in [
            "trademark_risk",
            "platform_policy_risk",
            "patent_claim_risk",
            "litigation_risk",
        ]:
            lines.append(
                f"| {d} | {m.get(d+'_accuracy',0):.3f} | {m.get(d+'_high_risk_recall',0):.3f} | {m.get(d+'_unknown_handling_accuracy',0):.3f} | {m.get(d+'_false_positive_rate',0):.3f} | {m.get(d+'_false_negative_rate',0):.3f} |"
            )

    lines += [
        "",
        "## 3. Response Evaluation",
        "| Faithfulness | Answer Relevance | Unsupported Claim Rate | Citation Coverage | Disclaimer Coverage | Forbidden Claim Rate |",
        "|---:|---:|---:|---:|---:|---:|",
    ]
    if response_result:
        rm = response_result.get("metrics", {})
        lines.append(
            f"| {rm.get('faithfulness',0):.3f} | {rm.get('answer_relevance',0):.3f} | {rm.get('unsupported_claim_rate',0):.3f} | {rm.get('citation_coverage',0):.3f} | {rm.get('disclaimer_coverage',0):.3f} | {rm.get('forbidden_claim_rate',0):.3f} |"
        )

    lines += [
        "",
        "## Chinese Response Evaluation",
        "| Chinese Answer Rate | Chinese Disclaimer Coverage | Brand Preservation | Mixed Language Penalty |",
        "|---:|---:|---:|---:|",
    ]
    if response_result:
        rm = response_result.get("metrics", {})
        lines.append(
            f"| {rm.get('chinese_answer_rate',0):.3f} | {rm.get('chinese_disclaimer_coverage',0):.3f} | {rm.get('brand_preservation',0):.3f} | {rm.get('mixed_language_penalty',0):.3f} |"
        )

    lines += [
        "",
        "## 4. Failure Cases",
        "- 检索失败样例：见 retrieval per_query 中 recall_at_k=0 的条目。",
        "- 风险误判样例：见 risk per_sample 中 expected != predicted 的条目。",
        "- unsupported 样例：见 response per_sample 中 unsupported_claim_rate>0 的条目。",
        "",
        "## 5. Summary",
        "- 检索瓶颈优先看低 recall 模块。",
        "- Reranker 提升需结合 latency 一起判断。",
        "- 风险判断可能偏保守，unknown 样例需人工复核。",
        "- 生成回答应持续降低 unsupported claim 风险。",
    ]
    text = "\n".join(lines) + "\n"
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(text, encoding="utf-8")
    return text
