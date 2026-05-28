from __future__ import annotations

from src.agents.llm_client import LLMClient
from src.decision.litigation_risk import assess_litigation_risk
from src.decision.patent_claim_risk import assess_patent_claim_risk
from src.decision.platform_policy_risk import assess_platform_policy_risk
from src.decision.trademark_risk import assess_trademark_risk


class RiskJudgeAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()

    def judge(self, evidence_bundle: dict) -> dict:
        parsed = evidence_bundle["parsed_listing"]
        tm_matches = evidence_bundle.get("trademark_matches", [])
        tm = assess_trademark_risk(parsed, tm_matches)
        pp = assess_platform_policy_risk(evidence_bundle.get("platform_policy_evidence", []))
        pc = assess_patent_claim_risk(evidence_bundle.get("patent_claim_evidence", []))
        patent_ids = list({x.metadata.get("patent_id", "") for x in evidence_bundle.get("patent_claim_evidence", []) if x.metadata})
        lit = assess_litigation_risk([x for x in patent_ids if x]) if patent_ids else {"overall_risk": "unknown", "results": []}

        dims = {
            "trademark_risk": tm.risk_level,
            "platform_policy_risk": pp["risk_level"],
            "patent_claim_risk": pc["risk_level"],
            "litigation_risk": lit["overall_risk"],
        }
        vals = list(dims.values())
        overall = "unknown"
        if "high" in vals:
            overall = "high"
        elif vals.count("medium") >= 2:
            overall = "high"
        elif "medium" in vals:
            overall = "medium"
        elif "low" in vals and all(v in {"low", "unknown"} for v in vals):
            overall = "low"

        reasons = [tm.reason, pp["reason"], pc["reason"]]
        confidence = 4 if overall != "unknown" else 2
        needs_llm = len([v for v in vals if v in {"high", "medium"}]) >= 2
        needs_second = overall == "unknown"

        if needs_llm and self.llm.is_enabled():
            fb = {"overall_risk": overall, "confidence": confidence, "reason": "rule-based"}
            _ = self.llm.chat_json([
                {"role": "system", "content": "Only output JSON. Judge risk based on provided evidence only. Never claim infringement established and never claim completely safe."},
                {"role": "user", "content": str({"dimension_risks": dims, "reasons": reasons})},
            ], fallback=fb)

        return {
            "overall_risk": overall,
            "dimension_risks": dims,
            "confidence": confidence,
            "needs_second_retrieval": needs_second,
            "reasons": reasons,
        }
