"""Text cleaning helpers for ingestion and normalization."""

from __future__ import annotations

import re

_WHITESPACE_RE = re.compile(r"\s+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
_PATENT_PREFIX_RE = re.compile(r"^(us|ep|wo|cn|jp|kr)")


def remove_extra_spaces(text: str) -> str:
    """Collapse consecutive whitespace and strip boundaries."""
    return _WHITESPACE_RE.sub(" ", text).strip()


def safe_lower(text: str) -> str:
    """Lowercase a string safely; empty input returns empty output."""
    return (text or "").lower()


def normalize_text(text: str) -> str:
    """Normalize generic text by lowering and removing extra spaces."""
    return remove_extra_spaces(safe_lower(text))


def normalize_mark(text: str) -> str:
    """Normalize trademark-like terms for robust matching."""
    lowered = normalize_text(text)
    tokenized = _NON_ALNUM_RE.sub(" ", lowered)
    return remove_extra_spaces(tokenized)


def normalize_patent_id(text: str) -> str:
    """Normalize patent id into compact uppercase style."""
    normalized = re.sub(r"[^a-zA-Z0-9]", "", text or "")
    if not normalized:
        return ""
    lowered = normalized.lower()
    # Keep known country/region prefixes then uppercase.
    if _PATENT_PREFIX_RE.match(lowered):
        return lowered.upper()
    return normalized.upper()
