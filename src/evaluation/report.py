from __future__ import annotations

from pathlib import Path
from typing import Any


def _pct(v: float) -> str:
    return f"{v * 100:.2f}%"


def build_markdown_report(retrieval_result: dict[str, Any], risk_result: dict[str, Any], out_path: str = "reports/evaluation_report.md") -> str:
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    r_m = retrieval_result.get("metrics", {})
    k_m = risk_result.get("metrics", {})
    risk_rows = risk_result.get("samples", [])

    unsupported_claim_rate = 1.0 - float(k_m.get("patent_claim_risk_accuracy", 0.0))
    citation_coverage = float(r_m.get("overall_hit_rate", 0.0))
    failed = [x for x in risk_rows if not x.get("correct", False)]

    lines = [
        "# Evaluation Report",
        "",
        f"- Total Samples: {k_m.get('total_samples', 0)}",
        "",
        "## Retrieval Metrics",
        f"- Trademark Hit Rate: {_pct(float(r_m.get('trademark_hit_rate', 0.0)))}",
        f"- Platform Policy Recall@K: {_pct(float(r_m.get('platform_policy_recall_at_k', 0.0)))}",
        f"- Claim Retrieval Recall@K: {_pct(float(r_m.get('claim_retrieval_recall_at_k', 0.0)))}",
        f"- Litigation Patent Hit Rate: {_pct(float(r_m.get('litigation_patent_hit_rate', 0.0)))}",
        "",
        "## Risk Judgment Metrics",
        f"- Trademark Risk Accuracy: {_pct(float(k_m.get('trademark_risk_accuracy', 0.0)))}",
        f"- High-risk Recall: {_pct(float(k_m.get('high_risk_recall', 0.0)))}",
        f"- Patent Claim Risk Accuracy: {_pct(float(k_m.get('patent_claim_risk_accuracy', 0.0)))}",
        f"- Litigation Risk Accuracy: {_pct(float(k_m.get('litigation_risk_accuracy', 0.0)))}",
        f"- Unknown Handling: {_pct(float(k_m.get('unknown_handling_accuracy', 0.0)))}",
        "",
        "## Additional Quality Signals",
        f"- Unsupported Claim Rate: {_pct(unsupported_claim_rate)}",
        f"- Citation Coverage: {_pct(citation_coverage)}",
        f"- Unknown Handling: {_pct(float(k_m.get('unknown_handling_accuracy', 0.0)))}",
        "",
        "## Failed Cases",
    ]
    if not failed:
        lines.append("- None")
    else:
        for row in failed:
            lines.append(
                f"- {row.get('id','')} | tm: {row.get('tm_expected')} -> {row.get('tm_pred')} | "
                f"claim: {row.get('pc_expected')} -> {row.get('pc_pred')} | lit: {row.get('lit_expected')} -> {row.get('lit_pred')}"
            )

    text = "\n".join(lines) + "\n"
    Path(out_path).write_text(text, encoding="utf-8")
    return text
