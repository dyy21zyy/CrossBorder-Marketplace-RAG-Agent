from __future__ import annotations

import os
from pathlib import Path

import pandas as pd

from src.schemas import ListingInput

INDEX_HINTS = {
    "trademark": "python scripts/01_build_trademark_db.py --sample --force_rebuild",
    "platform_policy": "python scripts/02_build_platform_index.py",
    "patent_claim": "python scripts/03_build_claim_index.py --sample --limit 50000",
    "litigation": "python scripts/04_build_litigation_db.py --sample --force_rebuild",
}


def _risk_badge(level: str) -> str:
    color = {"high": "🔴", "medium": "🟠", "low": "🟢", "unknown": "⚪"}.get(level, "⚪")
    return f"{color} **{level.upper()}**"


def _detect_missing(evidence_bundle: dict) -> list[str]:
    keys = {
        "trademark_evidence": "trademark",
        "platform_policy_evidence": "platform_policy",
        "patent_claim_evidence": "patent_claim",
        "litigation_evidence": "litigation",
    }
    missing: list[str] = []
    for ev_key, source in keys.items():
        if any((x.evidence_type == "system" and "Please run" in x.snippet) for x in evidence_bundle.get(ev_key, [])):
            missing.append(source)
    return missing


def run_pipeline(listing: ListingInput, enable_patent_check: bool, enable_litigation_check: bool, mock_llm: bool) -> tuple[dict, dict, list[dict], object]:
    from src.agents.evidence_agent import EvidenceAgent
    from src.agents.final_answer_agent import FinalAnswerAgent
    from src.agents.listing_rewrite_agent import ListingRewriteAgent
    from src.agents.query_router_agent import QueryRouter
    from src.agents.risk_judge_agent import RiskJudgeAgent

    os.environ["MOCK_LLM"] = "true" if mock_llm else "false"
    query = f"{listing.title} {listing.description} {listing.category} {listing.platform}"
    routed = QueryRouter().route(query)
    evidence_bundle = EvidenceAgent().collect(
        listing_input=listing,
        routed_intents=routed.get("intents", []),
        enable_patent_check=enable_patent_check,
        enable_litigation_check=enable_litigation_check,
    )
    risk = RiskJudgeAgent().judge(evidence_bundle)
    rewrite = ListingRewriteAgent().rewrite(listing, risk, evidence_bundle)
    answer = FinalAnswerAgent().generate(listing, evidence_bundle, risk, rewrite)
    return evidence_bundle, risk, rewrite, answer


def main() -> None:
    import streamlit as st

    st.set_page_config(page_title="CrossBorder Marketplace RAG Agent", layout="wide")
    st.title("CrossBorder Marketplace RAG Agent")

    with st.form("listing_form"):
        title = st.text_input("title", "Phone case compatible with iPhone 15")
        description = st.text_area("description", "Magnetic transparent phone case for iPhone 15")
        category = st.text_input("category", "phone accessory")
        platform = st.text_input("platform", "Temu")
        has_authorization = st.checkbox("has_authorization", value=False)
        enable_patent_check = st.checkbox("enable_patent_check", value=False)
        enable_litigation_check = st.checkbox("enable_litigation_check", value=False)
        mock_llm = st.checkbox("mock_llm", value=True)
        submitted = st.form_submit_button("Run Risk Screening")

    if not submitted:
        st.info("Fill the form and click 'Run Risk Screening' to start demo.")
        return

    listing = ListingInput(
        title=title,
        description=description,
        category=category,
        platform=platform,
        has_authorization=has_authorization,
    )
    evidence_bundle, risk, rewrite, answer = run_pipeline(listing, enable_patent_check, enable_litigation_check, mock_llm)

    st.subheader("Overall Risk badge")
    st.markdown(_risk_badge(risk.get("overall_risk", "unknown")))

    st.subheader("Risk Dimensions")
    dims = risk.get("dimension_risks", {})
    c1, c2, c3, c4 = st.columns(4)
    c1.markdown(f"Trademark Risk: {_risk_badge(dims.get('trademark_risk', 'unknown'))}")
    c2.markdown(f"Platform Policy Risk: {_risk_badge(dims.get('platform_policy_risk', 'unknown'))}")
    c3.markdown(f"Patent Claim Risk: {_risk_badge(dims.get('patent_claim_risk', 'unknown'))}")
    c4.markdown(f"Litigation Risk: {_risk_badge(dims.get('litigation_risk', 'unknown'))}")

    st.subheader("Evidence")
    rows: list[dict] = []
    for key in ["trademark_evidence", "platform_policy_evidence", "patent_claim_evidence", "litigation_evidence"]:
        for item in evidence_bundle.get(key, []):
            rows.append(
                {
                    "source_type": item.evidence_type,
                    "source": item.source,
                    "score": round(float(item.score), 4),
                    "metadata": item.metadata,
                    "snippet": item.snippet,
                }
            )
    st.dataframe(pd.DataFrame(rows), use_container_width=True)

    st.subheader("Rewrite Suggestions")
    for idx, item in enumerate(rewrite, start=1):
        st.markdown(f"{idx}. **{item['title']}**  ")
        st.caption(item["reason"])

    st.subheader("Final Answer")
    st.write(answer.summary)

    st.subheader("Disclaimer")
    st.warning((answer.disclaimers or ["This system is for preliminary IP risk screening only and does not constitute legal advice."])[0])

    missing = _detect_missing(evidence_bundle)
    if missing:
        st.error("Some indexes are missing. Build them first:")
        for m in missing:
            st.code(INDEX_HINTS[m], language="bash")


if __name__ == "__main__":
    main()
