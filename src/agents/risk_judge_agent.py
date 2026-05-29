from __future__ import annotations

from collections import Counter
from typing import Any

from src.agents.llm_client import LLMClient
from src.decision.litigation_risk import assess_litigation_risk
from src.decision.patent_claim_risk import assess_patent_claim_risk
from src.decision.platform_policy_risk import assess_platform_policy_risk
from src.decision.trademark_risk import assess_trademark_risk
from src.schemas import EvidenceItem, ParsedListing, TrademarkMatch

DIMENSIONS = (
    "trademark_risk",
    "platform_policy_risk",
    "patent_claim_risk",
    "litigation_risk",
)
STYLE_PATTERNS = ("style", "inspired by", "look alike", "replica", "dupe")
COMPAT_PATTERNS = (
    "compatible with",
    "for",
    "replacement for",
    "works with",
    "similar to",
)


class RiskJudgeAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()

    def _source_types(self, evidences: list[EvidenceItem]) -> list[str]:
        return sorted({e.evidence_type or e.source or "unknown" for e in evidences})

    def _has_non_system_evidence(self, evidences: list[EvidenceItem]) -> bool:
        return any(e.evidence_type != "system" for e in evidences)

    def _brand_in_title(
        self, parsed: ParsedListing, tm_matches: list[TrademarkMatch]
    ) -> bool:
        title = (parsed.title or parsed.normalized_title or "").lower()
        terms = set(parsed.candidate_brand_terms or []) | set(parsed.brand_terms or [])
        for match in tm_matches:
            terms.update([match.term, match.mark_id_char, match.mark])
        return any(term and term.lower() in title for term in terms)

    def _trademark_dimension(
        self,
        parsed: ParsedListing,
        tm_matches: list[TrademarkMatch],
        evidences: list[EvidenceItem],
    ) -> dict[str, Any]:
        base = assess_trademark_risk(parsed, tm_matches)
        candidate_brand_terms = [
            x for x in (parsed.candidate_brand_terms or parsed.brand_terms or []) if x
        ]
        has_direct_tm = bool(tm_matches) or self._has_non_system_evidence(evidences)
        brand_detected = bool(candidate_brand_terms) or bool(tm_matches)
        brand_in_title = self._brand_in_title(parsed, tm_matches)
        risk_text = " | ".join(parsed.risk_patterns or []).lower()
        has_style = any(pattern in risk_text for pattern in STYLE_PATTERNS)
        has_compat = any(pattern in risk_text for pattern in COMPAT_PATTERNS)
        exact_live_match = any(
            (
                m.match_type == "exact"
                and (
                    "live" in (m.status or "").lower()
                    or "registered" in (m.status or "").lower()
                )
            )
            for m in tm_matches
        )

        level = base.risk_level
        rules = set(base.triggered_rules)
        reason = base.reason

        if exact_live_match and not parsed.has_authorization and brand_in_title:
            level = "high"
            rules.add("direct_trademark_match_no_authorization_brand_in_title")
            reason = "Direct trademark match, no authorization, and brand term appears in the listing title; high preliminary trademark risk."
        elif has_style and brand_detected and not parsed.has_authorization:
            level = "high" if has_direct_tm else "medium-high"
            rules.add("style_inspired_lookalike_replica_dupe_brand_pattern")
            reason = "Brand term appears with style/inspired/look-alike/replica/dupe wording; high risk requires direct trademark evidence, otherwise medium-high screening risk."
        elif has_compat and brand_detected and not parsed.has_authorization:
            level = "medium-high"
            rules.add("compatible_with_brand_no_authorization")
            reason = "Brand term appears with compatibility wording and no authorization; this is medium-high screening risk, not a legal conclusion."
        elif brand_detected and not has_direct_tm:
            level = "medium"
            rules.add("brand_term_detected_without_direct_trademark_evidence")
            reason = "Brand term was detected, but no direct trademark evidence was retrieved; based on rule screening only."
        elif not has_direct_tm and level == "high":
            level = "medium-high"
            rules.add("downgraded_no_direct_trademark_evidence")
            reason = "No direct trademark evidence was retrieved, so the screening result is not escalated to high."

        confidence = (
            4
            if has_direct_tm and level in {"high", "medium-high"}
            else 3 if brand_detected else 2
        )
        return self._dimension_result(
            "trademark_risk",
            level,
            confidence,
            evidences or base.evidences,
            reason,
            sorted(rules),
        )

    def _dimension_result(
        self,
        risk_type: str,
        risk_level: str,
        confidence: int,
        evidences: list[EvidenceItem],
        reason: str,
        triggered_rules: list[str] | None = None,
    ) -> dict[str, Any]:
        return {
            "risk_type": risk_type,
            "risk_level": risk_level,
            "confidence": max(1, min(5, int(confidence))),
            "evidence_count": len(evidences),
            "evidence_source_types": self._source_types(evidences),
            "reason": reason,
            "triggered_rules": triggered_rules or [],
        }

    def _litigation_dimension(
        self, lit: dict[str, Any], evidences: list[EvidenceItem]
    ) -> dict[str, Any]:
        results = lit.get("results", []) or []
        max_case_count = max(
            [int(x.get("case_count", 0) or 0) for x in results], default=0
        )
        plaintiffs = [
            str(x.get("plaintiff_names", "")).strip()
            for x in results
            if str(x.get("plaintiff_names", "")).strip()
        ]
        repeated_plaintiff = any(count >= 3 for count in Counter(plaintiffs).values())
        level = str(lit.get("overall_risk", "unknown"))
        if max_case_count >= 3 or repeated_plaintiff:
            level = "high"
        elif not results and not evidences:
            level = "unknown"
        confidence = 4 if level == "high" else 3 if results else 2
        reason = (
            "Litigation case_count >= 3 or high-frequency plaintiff indicates high screening risk."
            if level == "high"
            else "Litigation risk is based on retrieved litigation summaries only; absence of records is not a legal clearance."
        )
        return self._dimension_result(
            "litigation_risk", level, confidence, evidences, reason
        )

    def _aggregate_overall(self, dimension_risks: dict[str, dict[str, Any]]) -> str:
        levels = [
            str(dimension_risks[dim].get("risk_level", "unknown")) for dim in DIMENSIONS
        ]
        if "high" in levels:
            return "high"
        if "medium-high" in levels:
            return "medium-high"
        if levels.count("medium") >= 2:
            return "medium-high"
        if "medium" in levels:
            return "medium"
        if "low" in levels and all(level in {"low", "unknown"} for level in levels):
            return "low"
        return "unknown"

    def judge(self, evidence_bundle: dict) -> dict:
        parsed = evidence_bundle["parsed_listing"]
        tm_matches = evidence_bundle.get("trademark_matches", [])
        trademark_evidence = evidence_bundle.get("trademark_evidence", [])
        platform_evidence = evidence_bundle.get("platform_policy_evidence", [])
        patent_evidence = evidence_bundle.get("patent_claim_evidence", [])
        litigation_evidence = evidence_bundle.get("litigation_evidence", [])

        pp = assess_platform_policy_risk(platform_evidence)
        pc = assess_patent_claim_risk(patent_evidence)
        if platform_evidence and not self._has_non_system_evidence(platform_evidence):
            pp = {
                "risk_type": "platform_policy",
                "risk_level": "unknown",
                "reason": "No usable platform policy evidence retrieved; index may be unavailable.",
            }
        if patent_evidence and not self._has_non_system_evidence(patent_evidence):
            pc = {
                "risk_type": "patent_claim",
                "risk_level": "unknown",
                "reason": "No usable patent claim evidence retrieved; index may be unavailable.",
            }
        patent_ids = list(
            {x.metadata.get("patent_id", "") for x in patent_evidence if x.metadata}
        )
        lit = (
            assess_litigation_risk([x for x in patent_ids if x])
            if patent_ids
            else {"overall_risk": "unknown", "results": []}
        )

        dimension_risks = {
            "trademark_risk": self._trademark_dimension(
                parsed, tm_matches, trademark_evidence
            ),
            "platform_policy_risk": self._dimension_result(
                "platform_policy_risk",
                str(pp["risk_level"]),
                3 if self._has_non_system_evidence(platform_evidence) else 2,
                platform_evidence,
                str(pp["reason"]),
            ),
            "patent_claim_risk": self._dimension_result(
                "patent_claim_risk",
                str(pc["risk_level"]),
                3 if self._has_non_system_evidence(patent_evidence) else 2,
                patent_evidence,
                str(pc["reason"]),
            ),
            "litigation_risk": self._litigation_dimension(lit, litigation_evidence),
        }

        overall = self._aggregate_overall(dimension_risks)
        confidence = (
            max(
                [int(x.get("confidence", 1)) for x in dimension_risks.values()],
                default=2,
            )
            if overall != "unknown"
            else 2
        )
        risk_results = [dimension_risks[dim] for dim in DIMENSIONS]
        needs_second = any(
            x["risk_level"] == "unknown" and x["evidence_count"] == 0
            for x in risk_results
        )
        reasons = [x["reason"] for x in risk_results]

        if (
            self.llm.is_enabled()
            and len(
                [
                    x
                    for x in risk_results
                    if x["risk_level"] in {"high", "medium-high", "medium"}
                ]
            )
            >= 2
        ):
            fb = {
                "overall_risk": overall,
                "confidence": confidence,
                "reason": "rule-based",
            }
            _ = self.llm.chat_json(
                [
                    {
                        "role": "system",
                        "content": "Only output JSON. Judge risk based on provided evidence only. Never claim infringement established and never claim completely safe.",
                    },
                    {
                        "role": "user",
                        "content": str(
                            {"dimension_risks": dimension_risks, "reasons": reasons}
                        ),
                    },
                ],
                fallback=fb,
            )

        return {
            "overall_risk": overall,
            "dimension_risks": dimension_risks,
            "risk_results": risk_results,
            "confidence": confidence,
            "needs_second_retrieval": needs_second,
            "reasons": reasons,
        }
