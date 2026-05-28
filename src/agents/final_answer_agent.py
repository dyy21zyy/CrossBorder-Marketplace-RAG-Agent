from __future__ import annotations

import json
from pathlib import Path

from src.agents.llm_client import LLMClient
from src.schemas import EvidenceItem, FinalAnswer, ListingInput

DISCLAIMER = "This system is for preliminary IP risk screening only and does not constitute legal advice."


class FinalAnswerAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()
        self.prompt_path = Path(__file__).resolve().parents[2] / "prompts" / "final_answer.md"

    def _compact_evidence(self, evidences: list[EvidenceItem], limit: int = 3) -> list[dict]:
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

    def _build_payload(self, listing: ListingInput, evidence_bundle: dict, risk_result: dict, rewrite_suggestions: list[dict]) -> dict:
        return {
            "listing": listing.model_dump(),
            "risk_result": risk_result,
            "rewrite_suggestions": rewrite_suggestions,
            "evidence": {
                "trademark": self._compact_evidence(evidence_bundle.get("trademark_evidence", [])),
                "platform_policy": self._compact_evidence(evidence_bundle.get("platform_policy_evidence", [])),
                "patent_claim": self._compact_evidence(evidence_bundle.get("patent_claim_evidence", [])),
                "litigation": self._compact_evidence(evidence_bundle.get("litigation_evidence", [])),
            },
        }

    def _template_answer(self, risk_result: dict, rewrite_suggestions: list[dict], payload: dict) -> FinalAnswer:
        dims = risk_result.get("dimension_risks", {})
        overall = risk_result.get("overall_risk", "unknown")
        suggestion_lines = [f"- {x['title']}: {x['reason']}" for x in rewrite_suggestions]
        evidence_used = []
        for dim, rows in payload.get("evidence", {}).items():
            for row in rows:
                evidence_used.append(f"{dim} | {row['source']} | score={row['score']}")

        summary = "\n".join(
            [
                f"Overall Risk: {overall}. evidence suggests a preliminary risk profile and may require manual review.",
                f"Trademark Risk: {dims.get('trademark_risk', 'unknown')} (potential risk based on retrieved trademark evidence).",
                f"Platform Policy Risk: {dims.get('platform_policy_risk', 'unknown')} (evidence suggests policy-sensitive wording may exist).",
                f"Patent Claim Risk: {dims.get('patent_claim_risk', 'unknown')} (not enough evidence to make legal conclusions).",
                f"Litigation Risk: {dims.get('litigation_risk', 'unknown')} (historical records may require manual review).",
                "Evidence Used: " + ("; ".join(evidence_used) if evidence_used else "not enough evidence."),
                "Listing Revision Suggestions:\n" + ("\n".join(suggestion_lines) if suggestion_lines else "- unknown"),
                "Uncertainty: This is a screening outcome; unknown applies where evidence is insufficient.",
                f"Disclaimer: {DISCLAIMER}",
            ]
        )
        return FinalAnswer(
            summary=summary,
            overall_risk_level=overall,
            risk_results=[],
            rewrite_suggestions=[x["title"] for x in rewrite_suggestions],
            disclaimers=[DISCLAIMER],
        )

    def generate(self, listing: ListingInput, evidence_bundle: dict, risk_result: dict, rewrite_suggestions: list[dict]) -> FinalAnswer:
        payload = self._build_payload(listing, evidence_bundle, risk_result, rewrite_suggestions)
        if self.llm.mock_llm or not self.llm.is_enabled():
            return self._template_answer(risk_result, rewrite_suggestions, payload)

        try:
            prompt = self.prompt_path.read_text(encoding="utf-8")
            raw = self.llm.chat(
                [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                ]
            )
            if not raw:
                return self._template_answer(risk_result, rewrite_suggestions, payload)
            if DISCLAIMER not in raw:
                raw += f"\n\nDisclaimer: {DISCLAIMER}"
            return FinalAnswer(
                summary=raw,
                overall_risk_level=risk_result.get("overall_risk", "unknown"),
                risk_results=[],
                rewrite_suggestions=[x["title"] for x in rewrite_suggestions],
                disclaimers=[DISCLAIMER],
            )
        except Exception:
            return self._template_answer(risk_result, rewrite_suggestions, payload)
