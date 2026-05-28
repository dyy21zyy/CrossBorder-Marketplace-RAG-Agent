from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.agents.evidence_agent import EvidenceAgent
from src.agents.query_router_agent import QueryRouter
from src.agents.risk_judge_agent import RiskJudgeAgent
from src.schemas import ListingInput


def _load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def evaluate_risk(path: str = "data/eval/risk_eval.jsonl", enable_patent_check: bool = False, enable_litigation_check: bool = False) -> dict[str, Any]:
    samples = _load_jsonl(path)
    router = QueryRouter()
    evidence_agent = EvidenceAgent()
    judge = RiskJudgeAgent()

    rows: list[dict[str, Any]] = []
    tm_ok = high_risk_hit = tm_high_total = 0
    pc_ok = lit_ok = unknown_ok = 0

    for s in samples:
        listing = ListingInput(
            title=str(s.get("title", "")),
            description=str(s.get("description", "")),
            category=str(s.get("category", "")),
            platform=str(s.get("platform", "Temu")),
            has_authorization=bool(s.get("has_authorization", False)),
        )
        query = f"{listing.title} {listing.description} {listing.category} {listing.platform}".strip()
        routed = router.route(query)
        ev = evidence_agent.collect(listing, routed.get("intents", []), enable_patent_check=enable_patent_check, enable_litigation_check=enable_litigation_check)
        pred = judge.judge(ev)

        exp_tm = str(s.get("expected_trademark_risk", "unknown"))
        exp_pc = str(s.get("expected_patent_claim_risk", "unknown"))
        exp_lit = str(s.get("expected_litigation_risk", "unknown"))

        got_tm = str(pred.get("dimension_risks", {}).get("trademark_risk", "unknown"))
        got_pc = str(pred.get("dimension_risks", {}).get("patent_claim_risk", "unknown"))
        got_lit = str(pred.get("dimension_risks", {}).get("litigation_risk", "unknown"))

        tm_match = exp_tm == got_tm
        pc_match = exp_pc == got_pc
        lit_match = exp_lit == got_lit
        unknown_match = (exp_tm == "unknown" and got_tm == "unknown") or (exp_pc == "unknown" and got_pc == "unknown") or (exp_lit == "unknown" and got_lit == "unknown")

        tm_ok += int(tm_match)
        pc_ok += int(pc_match)
        lit_ok += int(lit_match)
        unknown_ok += int(unknown_match)
        if exp_tm == "high":
            tm_high_total += 1
            high_risk_hit += int(got_tm == "high")

        rows.append({"id": s.get("id", ""), "tm_expected": exp_tm, "tm_pred": got_tm, "pc_expected": exp_pc, "pc_pred": got_pc, "lit_expected": exp_lit, "lit_pred": got_lit, "correct": tm_match and pc_match and lit_match})

    n = max(1, len(samples))
    metrics = {
        "total_samples": len(samples),
        "trademark_risk_accuracy": tm_ok / n,
        "high_risk_recall": (high_risk_hit / tm_high_total) if tm_high_total else 0.0,
        "patent_claim_risk_accuracy": pc_ok / n,
        "litigation_risk_accuracy": lit_ok / n,
        "unknown_handling_accuracy": unknown_ok / n,
        "overall_accuracy": sum(int(x["correct"]) for x in rows) / n,
    }
    return {"samples": rows, "metrics": metrics}
