"""Section-aware chunking for Temu IP policy."""

from __future__ import annotations

import re
from typing import Any

SECTION_KEYWORDS: dict[str, list[str]] = {
    "trademark": ["trademark", "counterfeit", "brand"],
    "copyright": ["copyright", "dmca"],
    "patent": ["patent", "utility model", "design patent"],
    "report infringement": ["report infringement", "report violation", "submit a complaint"],
    "counter notice": ["counter notice", "counter-notice", "counter notification"],
    "enforcement": ["enforcement", "penalty", "remove listing", "suspension"],
    "repeat infringement": ["repeat infringement", "repeat offender", "multiple violations"],
}


HEADER_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)*)?\s*([A-Za-z][A-Za-z\s\-/]{2,80})\s*$")


def _guess_section(text: str, current_section: str = "general") -> str:
    low = text.lower()
    for section, keywords in SECTION_KEYWORDS.items():
        if any(k in low for k in keywords):
            return section
    if HEADER_PATTERN.match(text.strip()):
        candidate = text.strip().lower()
        for section in list(SECTION_KEYWORDS.keys()) + ["general"]:
            if section in candidate:
                return section
    return current_section


def _split_paragraphs(text: str) -> list[str]:
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    return paras


def chunk_platform_policy(
    pages: list[dict[str, Any]],
    max_chars: int = 1200,
) -> list[dict[str, Any]]:
    """Create section-aware chunks with context and metadata."""
    chunks: list[dict[str, Any]] = []
    current_section = "general"
    carry: list[str] = []
    carry_pages: list[int] = []

    def flush() -> None:
        if not carry:
            return
        page_start = min(carry_pages)
        page_end = max(carry_pages)
        chunk_text = "\n\n".join(carry).strip()
        context_path = (
            f"[Temu IP Policy > {current_section}]\n"
            "Platform: Temu\n"
            "Source Type: official\n"
            f"Page: {page_start}-{page_end}\n"
            "Authority: high"
        )
        chunk_id = f"temu_policy_p{page_start}_{page_end}_{len(chunks)+1}"
        chunks.append(
            {
                "chunk_id": chunk_id,
                "text": chunk_text,
                "context_path": context_path,
                "source": "Temu IP Policy",
                "platform": "Temu",
                "source_type": "official",
                "authority_level": "high",
                "rule_type": "ip_policy",
                "ip_type": current_section if current_section in {"trademark", "copyright", "patent"} else "general",
                "section": current_section,
                "page_start": page_start,
                "page_end": page_end,
                "metadata": {
                    "source": "Temu IP Policy",
                    "platform": "Temu",
                    "source_type": "official",
                    "authority_level": "high",
                    "rule_type": "ip_policy",
                    "ip_type": current_section if current_section in {"trademark", "copyright", "patent"} else "general",
                    "section": current_section,
                    "page_start": page_start,
                    "page_end": page_end,
                },
            }
        )

    for page in pages:
        page_num = int(page["page_number"])
        paras = _split_paragraphs(str(page.get("text", "")))
        for para in paras:
            guessed = _guess_section(para, current_section)
            if guessed != current_section and carry:
                flush()
                carry.clear()
                carry_pages.clear()
            current_section = guessed

            projected = "\n\n".join(carry + [para])
            if carry and len(projected) > max_chars:
                flush()
                carry.clear()
                carry_pages.clear()

            carry.append(para)
            carry_pages.append(page_num)

    flush()
    return chunks
