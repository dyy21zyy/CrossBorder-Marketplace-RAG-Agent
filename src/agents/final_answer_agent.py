from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agents.llm_client import LLMClient
from src.schemas import EvidenceItem, FinalAnswer, ListingInput

DISCLAIMER = "This system is for preliminary IP risk screening only and does not constitute legal advice."


class FinalAnswerAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()
        self.prompt_path = (
            Path(__file__).resolve().parents[2] / "prompts" / "final_answer.md"
        )

    def _compact_evidence(
        self, evidences: list[EvidenceItem], limit: int = 3
    ) -> list[dict]:
        out: list[dict] = []
        for e in evidences[:limit]:
            out.append(
                {
                    "source_type": e.evidence_type,
                    "source": e.source,
                    "score": round(float(e.score), 4),
                    "metadata": e.metadata,
                    "text_snippet": (e.snippet or "")[:280],
                }
            )
        return out

    def _build_payload(
        self,
        listing: ListingInput,
        evidence_bundle: dict,
        risk_result: dict,
        rewrite_suggestions: list[dict],
    ) -> dict:
        return {
            "listing": listing.model_dump(),
            "risk_result": risk_result,
            "rewrite_suggestions": rewrite_suggestions,
            "evidence": {
                "trademark": self._compact_evidence(
                    evidence_bundle.get("trademark_evidence", [])
                ),
                "platform_policy": self._compact_evidence(
                    evidence_bundle.get("platform_policy_evidence", [])
                ),
                "patent_claim": self._compact_evidence(
                    evidence_bundle.get("patent_claim_evidence", [])
                ),
                "litigation": self._compact_evidence(
                    evidence_bundle.get("litigation_evidence", [])
                ),
            },
        }

    def _risk_results(self, risk_result: dict) -> list[dict[str, Any]]:
        risk_results = risk_result.get("risk_results") or []
        if risk_results:
            return risk_results
        dims = risk_result.get("dimension_risks", {})
        out: list[dict[str, Any]] = []
        for risk_type in [
            "trademark_risk",
            "platform_policy_risk",
            "patent_claim_risk",
            "litigation_risk",
        ]:
            value = dims.get(risk_type, "unknown")
            if isinstance(value, dict):
                row = dict(value)
                row.setdefault("risk_type", risk_type)
                row.setdefault("risk_level", "unknown")
            else:
                row = {
                    "risk_type": risk_type,
                    "risk_level": str(value),
                    "confidence": 1,
                    "evidence_count": 0,
                    "evidence_source_types": [],
                    "reason": "Risk result was normalized from legacy dimension output.",
                }
            out.append(row)
        return out

    def _dimension_level(
        self, risk_results: list[dict[str, Any]], risk_type: str
    ) -> str:
        for row in risk_results:
            if row.get("risk_type") == risk_type:
                return str(row.get("risk_level", "unknown"))
        return "unknown"

    def _has_direct_trademark_evidence(self, payload: dict) -> bool:
        return any(
            row.get("source_type") != "system"
            for row in payload.get("evidence", {}).get("trademark", [])
        )

    def _template_answer(
        self, risk_result: dict, rewrite_suggestions: list[dict], payload: dict
    ) -> FinalAnswer:
        risk_results = self._risk_results(risk_result)
        overall = risk_result.get("overall_risk", "unknown")
        suggestion_lines = [
            f"- {x['title']}: {x['reason']}" for x in rewrite_suggestions
        ]
        evidence_used = []
        for dim, rows in payload.get("evidence", {}).items():
            for row in rows:
                evidence_used.append(
                    f"{dim} | {row['source']} | {row['source_type']} | score={row['score']}"
                )

        direct_tm = self._has_direct_trademark_evidence(payload)
        trademark_basis = (
            "potential risk based on retrieved trademark evidence"
            if direct_tm
            else "brand-term risk found by rule screening; no direct trademark evidence was retrieved"
        )
        risk_lines = []
        for row in risk_results:
            label = row.get("risk_type", "unknown")
            level = row.get("risk_level", "unknown")
            confidence = row.get("confidence", 1)
            evidence_count = row.get("evidence_count", 0)
            sources = ",".join(row.get("evidence_source_types", [])) or "none"
            reason = row.get("reason", "")
            risk_lines.append(
                f"- {label}: {level}; confidence={confidence}/5; evidence_count={evidence_count}; evidence_source_types={sources}; reason={reason}"
            )

        summary = "\n".join(
            [
                f"Overall Risk: {overall}. This is a preliminary screening profile and should be manually reviewed.",
                f"Trademark Risk: {self._dimension_level(risk_results, 'trademark_risk')} ({trademark_basis}).",
                f"Platform Policy Risk: {self._dimension_level(risk_results, 'platform_policy_risk')} (platform policy evidence is treated as review-triggering, not a standalone legal conclusion).",
                f"Patent Claim Risk: {self._dimension_level(risk_results, 'patent_claim_risk')} (keyword or claim-retrieval overlap does not establish infringement).",
                f"Litigation Risk: {self._dimension_level(risk_results, 'litigation_risk')} (historical records may require manual review).",
                "Structured Risk Results:\n" + "\n".join(risk_lines),
                "Evidence Used: "
                + (
                    "; ".join(evidence_used)
                    if evidence_used
                    else "not enough evidence."
                ),
                "Listing Revision Suggestions:\n"
                + ("\n".join(suggestion_lines) if suggestion_lines else "- unknown"),
                "Uncertainty: Unknown applies where evidence is insufficient; this screening does not say the listing is completely safe.",
                f"Disclaimer: {DISCLAIMER}",
            ]
        )
        return FinalAnswer(
            summary=summary,
            overall_risk_level=overall,
            risk_results=risk_results,
            rewrite_suggestions=[x["title"] for x in rewrite_suggestions],
            disclaimers=[DISCLAIMER],
        )

    def generate(
        self,
        listing: ListingInput,
        evidence_bundle: dict,
        risk_result: dict,
        rewrite_suggestions: list[dict],
    ) -> FinalAnswer:
        payload = self._build_payload(
            listing, evidence_bundle, risk_result, rewrite_suggestions
        )
        risk_results = self._risk_results(risk_result)
        if (
            self.llm.mock_llm
            or not self.llm.is_enabled()
            or not self._has_direct_trademark_evidence(payload)
        ):
            return self._template_answer(risk_result, rewrite_suggestions, payload)

        try:
            prompt = self.prompt_path.read_text(encoding="utf-8")
            raw = self.llm.chat(
                [
                    {"role": "system", "content": prompt},
                    {
                        "role": "user",
                        "content": json.dumps(payload, ensure_ascii=False),
                    },
                ]
            )
            if not raw:
                return self._template_answer(risk_result, rewrite_suggestions, payload)

            summary = raw
            overall_risk_level = risk_result.get("overall_risk", "unknown")
            output_risk_results = risk_results
            output_rewrite_suggestions = [x["title"] for x in rewrite_suggestions]
            try:
                parsed = json.loads(self.llm._clean_json_response(raw))
                if isinstance(parsed, dict):
                    summary = str(parsed.get("summary") or parsed.get("answer") or raw)
                    overall_risk_level = str(
                        parsed.get("overall_risk_level")
                        or parsed.get("overall_risk")
                        or overall_risk_level
                    )
                    if isinstance(parsed.get("risk_results"), list):
                        output_risk_results = parsed["risk_results"]
                    if isinstance(parsed.get("rewrite_suggestions"), list):
                        output_rewrite_suggestions = [
                            str(item) for item in parsed["rewrite_suggestions"]
                        ]
            except Exception:
                summary = raw

            if DISCLAIMER not in summary:
                summary += f"\n\nDisclaimer: {DISCLAIMER}"
            return FinalAnswer(
                summary=summary,
                overall_risk_level=overall_risk_level,
                risk_results=output_risk_results,
                rewrite_suggestions=output_rewrite_suggestions,
                disclaimers=[DISCLAIMER],
            )
        except Exception:
            return self._template_answer(risk_result, rewrite_suggestions, payload)
