from __future__ import annotations

from src.retrieval.litigation_retriever import LitigationRetriever


def assess_litigation_risk(
    patent_ids: list[str],
    retriever: LitigationRetriever | None = None,
) -> dict[str, object]:
    r = retriever or LitigationRetriever()
    results: list[dict[str, object]] = []
    overall = "low"

    for patent_id in patent_ids:
        summary = r.get_litigation_summary(patent_id)
        if not summary:
            level = "low"
            status = "unknown"
            case_count = 0
            infringement_count = 0
            reason = "未检索到相关诉讼记录，当前为低风险筛查结论。"
        else:
            case_count = int(summary.get("case_count", 0) or 0)
            infringement_count = int(summary.get("infringement_case_count", 0) or 0)
            status = "known"
            if case_count >= 3:
                level = "high"
            elif case_count >= 1:
                level = "medium"
            else:
                level = "low"
            if infringement_count > 0 and level == "low":
                level = "medium"
            elif infringement_count > 0 and level == "medium" and case_count >= 2:
                level = "high"
            reason = "相关专利存在诉讼历史，需要关注；该结果不构成侵权认定或法律意见。"

        if level == "high" or (level == "medium" and overall == "low"):
            overall = level

        results.append(
            {
                "patent_id": patent_id,
                "normalized_patent": summary.get("normalized_patent", "") if summary else "",
                "record_status": status,
                "litigation_risk": level,
                "case_count": case_count,
                "infringement_case_count": infringement_count,
                "first_case_date": summary.get("first_case_date", "") if summary else "",
                "latest_case_date": summary.get("latest_case_date", "") if summary else "",
                "plaintiff_names": summary.get("plaintiff_names", "") if summary else "",
                "defendant_names": summary.get("defendant_names", "") if summary else "",
                "reason": reason,
            }
        )

    return {
        "risk_type": "litigation",
        "overall_risk": overall,
        "results": results,
        "disclaimer": "诉讼历史仅用于合规风险筛查，不代表对商品或卖家的侵权结论。",
    }
