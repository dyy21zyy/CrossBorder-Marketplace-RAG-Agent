from __future__ import annotations

from src.schemas import EvidenceItem


def assess_platform_policy_risk(evidences: list[EvidenceItem]) -> dict[str, object]:
    if not evidences:
        return {"risk_type": "platform_policy", "risk_level": "unknown", "reason": "No Temu IP Policy evidence retrieved."}
    return {
        "risk_type": "platform_policy",
        "risk_level": "medium",
        "reason": "Temu IP Policy evidence matched; platform compliance review needed.",
    }
