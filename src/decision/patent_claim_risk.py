from __future__ import annotations

from src.schemas import EvidenceItem


def assess_patent_claim_risk(evidences: list[EvidenceItem]) -> dict[str, object]:
    if not evidences:
        return {
            "risk_type": "patent_claim",
            "risk_level": "unknown",
            "reason": "No relevant claim group evidence retrieved.",
        }
    return {
        "risk_type": "patent_claim",
        "risk_level": "medium",
        "reason": "Relevant claim groups were retrieved; this indicates technical overlap only, not infringement.",
    }
