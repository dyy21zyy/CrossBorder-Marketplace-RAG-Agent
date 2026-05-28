from __future__ import annotations

import re

from src.agents.llm_client import LLMClient
from src.schemas import ListingInput

BANNED = ["style", "inspired by", "look alike", "fake", "replica", "dupe", "official", "authorized", "genuine", "authentic"]


class ListingRewriteAgent:
    def __init__(self, llm_client: LLMClient | None = None) -> None:
        self.llm = llm_client or LLMClient()

    def _sanitize(self, title: str) -> str:
        out = title
        for w in BANNED:
            out = re.sub(rf"\b{re.escape(w)}\b", "", out, flags=re.IGNORECASE)
        out = re.sub(r"compatible with", "designed for", out, flags=re.IGNORECASE)
        out = re.sub(r"\s+", " ", out).strip(" -_,")
        return out

    def rewrite(self, listing: ListingInput, risk_result: dict, evidence_bundle: dict) -> list[dict]:
        base = self._sanitize(listing.title)
        if not listing.has_authorization:
            for bt in evidence_bundle.get("parsed_listing").candidate_brand_terms:
                base = re.sub(rf"\b{re.escape(bt)}\b", "", base, flags=re.IGNORECASE).strip()
        base = re.sub(r"\s+", " ", base).strip(" -_,")
        s1 = f"{base}" if base else "Generic product title with key product attributes"
        s2 = f"{base} for daily use" if base else "Product accessory for daily use"
        s3 = f"{base} {listing.category}".strip() if listing.category else s2
        suggestions = [
            {"title": s1, "reason": "Removed high-risk wording and reduced implied affiliation claims."},
            {"title": s2, "reason": "Uses neutral function-focused phrasing and may require manual review."},
            {"title": s3, "reason": "Adds category context while avoiding misleading authorization language."},
        ]
        cleaned = []
        for s in suggestions:
            if not s["title"]:
                continue
            if any(x in s["title"].lower() for x in ["official", "authorized", "genuine", "authentic", "replica", "fake"]):
                continue
            cleaned.append(s)
        return cleaned[:3]
