from __future__ import annotations
from pathlib import Path
from typing import Any

def _row(m):
    return f"| {m['module']} | {m['recall_at_5']:.3f} | {m['precision_at_5']:.3f} | {m['mrr']:.3f} | {m['avg_context_relevance']:.3f} | {m['avg_latency_sec']:.3f} |"

def build_markdown_report(retrieval_result: dict[str, Any], risk_result: dict[str, Any], out_path: str = "reports/evaluation_report.md") -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    lines=["# Evaluation Report","","## Retrieval Evaluation","","### Without Reranker","| module | Recall@5 | Precision@5 | MRR | Context Relevance | Avg Latency |","|---|---:|---:|---:|---:|---:|"]
    for m in retrieval_result.get('no_reranker',[]): lines.append(_row(m))
    if retrieval_result.get('with_reranker'):
        lines += ["","### With Reranker","| module | Recall@5 | Precision@5 | MRR | Context Relevance | Avg Latency |","|---|---:|---:|---:|---:|---:|"]
        for m in retrieval_result.get('with_reranker',[]): lines.append(_row(m))
        lines += ["","### Reranker Improvement","| module | Recall@5 Δ | Precision@5 Δ | MRR Δ | Context Relevance Δ | Latency Δ |","|---|---:|---:|---:|---:|---:|"]
        for d in retrieval_result.get('improvement',[]): lines.append(f"| {d['module']} | {d['recall_at_5_delta']:.3f} | {d['precision_at_5_delta']:.3f} | {d['mrr_delta']:.3f} | {d['context_relevance_delta']:.3f} | {d['latency_delta']:.3f} |")
    lines += ["","## Risk Evaluation"]
    rn=risk_result.get('no_reranker',risk_result)
    lines += ["","### Without Reranker","| module | Accuracy | High-risk Recall | Citation Coverage | Unsupported Claim Rate |","|---|---:|---:|---:|---:|",f"| overall | {rn['metrics']['overall_risk_accuracy']:.3f} | {rn['metrics']['high_risk_recall']:.3f} | {rn['metrics']['citation_coverage']:.3f} | {rn['metrics']['unsupported_claim_rate']:.3f} |"]
    rw=risk_result.get('with_reranker')
    if rw:
        lines += ["","### With Reranker","| module | Accuracy | High-risk Recall | Citation Coverage | Unsupported Claim Rate |","|---|---:|---:|---:|---:|",f"| overall | {rw['metrics']['overall_risk_accuracy']:.3f} | {rw['metrics']['high_risk_recall']:.3f} | {rw['metrics']['citation_coverage']:.3f} | {rw['metrics']['unsupported_claim_rate']:.3f} |"]
    lines += ["","### Summary","- Reranker may improve ranking quality while increasing latency."]
    text='\n'.join(lines)+'\n'; Path(out_path).write_text(text,encoding='utf-8'); return text
