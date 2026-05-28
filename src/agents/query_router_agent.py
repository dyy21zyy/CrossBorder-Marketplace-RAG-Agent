from __future__ import annotations

import re

from src.agents.llm_client import LLMClient

INTENTS = ["trademark_risk", "platform_policy", "patent_claim_risk", "litigation_risk", "listing_rewrite"]


class QueryRouter:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()

    def _rule_route(self, query: str) -> dict:
        q = (query or "").lower()
        patterns = {
            "trademark_risk": [r"compatible with", r"\bfor\b", r"style", r"inspired by", r"replacement for", r"look alike", r"similar to", r"iphone", r"lego", r"nike", r"disney", r"apple", r"stanley", r"crocs", r"\b[A-Z]{2,}\b"],
            "platform_policy": [r"temu", r"policy", r"intellectual property", r"ip policy", r"report infringement", r"takedown", r"complaint"],
            "patent_claim_risk": [r"patent", r"claim", r"structure", r"mechanism", r"device", r"apparatus", r"method", r"foldable", r"magnetic", r"holder", r"stand", r"charger", r"battery"],
            "litigation_risk": [r"litigation", r"lawsuit", r"sued", r"case", r"dispute", r"plaintiff", r"defendant", r"court"],
            "listing_rewrite": [r"rewrite", r"revise", r"optimize", r"safer title", r"modify title", r"修改标题", r"降低风险"],
        }
        hits: dict[str, int] = {k: 0 for k in patterns}
        for intent, ps in patterns.items():
            for p in ps:
                if re.search(p, query if "[A-Z]" in p else q, flags=re.IGNORECASE):
                    hits[intent] += 1
        intents = [k for k, v in hits.items() if v > 0]
        confidence = min(5, max(1, sum(hits.values()))) if intents else 1
        return {"intents": intents or ["trademark_risk"], "confidence": confidence, "reason": f"rule_hits={hits}"}

    def route(self, query: str) -> dict:
        rule = self._rule_route(query)
        if self.llm.mock_llm:
            return rule
        ambiguous = len(rule["intents"]) == 0 or (len(rule["intents"]) > 2 and rule["confidence"] <= 3)
        if not ambiguous:
            return rule
        prompt = [
            {"role": "system", "content": "Classify query intent for cross-border risk agent. Return JSON only: {\"intents\": [...], \"confidence\": 1-5, \"reason\": \"...\"}."},
            {"role": "user", "content": f"Query: {query}\nAllowed intents: {INTENTS}"},
        ]
        llm = self.llm.chat_json(prompt, fallback=rule)
        intents = [x for x in llm.get("intents", []) if x in INTENTS]
        return {"intents": intents or rule["intents"], "confidence": int(llm.get("confidence", rule["confidence"])), "reason": str(llm.get("reason", ""))}
