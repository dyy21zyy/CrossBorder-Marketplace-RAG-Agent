from __future__ import annotations

from src.listing.category_mapper import map_category_to_nice_classes
from src.schemas import EvidenceItem, ParsedListing, RiskResult, TrademarkMatch


HIGH_PATTERNS = {"style", "inspired by", "look alike"}
COMPAT_PATTERNS = {"compatible with", "for", "replacement for", "works with", "similar to"}


def _is_live(status: str) -> bool:
    s = (status or "").lower()
    return "live" in s or "registered" in s


def assess_trademark_risk(parsed_listing: ParsedListing, trademark_matches: list[TrademarkMatch]) -> RiskResult:
    if not trademark_matches:
        return RiskResult(
            risk_type="trademark",
            risk_level="low",
            triggered_rules=["no_trademark_match"],
            reason="No direct trademark match found; result is risk screening only.",
            evidences=[],
        )

    rules: list[str] = []
    level = "low"
    evidences: list[EvidenceItem] = []

    listing_classes = set(map_category_to_nice_classes(parsed_listing.category or parsed_listing.inferred_category))
    rp_text = " | ".join(parsed_listing.risk_patterns).lower()

    for m in trademark_matches:
        if m.match_type == "exact" and not parsed_listing.has_authorization and _is_live(m.status):
            level = "high"
            rules.append("exact_match_no_authorization_live")
        elif m.match_type == "fuzzy" and not parsed_listing.has_authorization and level != "high":
            level = "medium"
            rules.append("fuzzy_match_no_authorization")

        if any(p in rp_text for p in HIGH_PATTERNS):
            level = "high"
            rules.append("style_inspired_lookalike_pattern")
        elif any(p in rp_text for p in COMPAT_PATTERNS) and level not in {"high"}:
            level = "medium"
            rules.append("compatibility_pattern")

        if listing_classes.intersection(set(m.intl_classes)):
            rules.append("category_relevance_high")

        evidences.append(
            EvidenceItem(
                evidence_id=f"tm-{m.serial_no}",
                evidence_type="trademark",
                source="trademark_case",
                title=m.mark_id_char,
                snippet=f"Term={m.term}; match={m.match_type}; status={m.status}; classes={','.join(m.intl_classes)}",
                score=m.match_score,
                metadata={"risk_screening": "potential risk"},
            )
        )

    reason = "Potential trademark risk identified by structured matching and rule screening; this is not a legal conclusion."
    return RiskResult(
        risk_type="trademark",
        risk_level=level,
        triggered_rules=sorted(set(rules)),
        reason=reason,
        evidences=evidences,
    )
