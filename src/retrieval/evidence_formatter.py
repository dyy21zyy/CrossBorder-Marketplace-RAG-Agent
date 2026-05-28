"""Evidence formatting helpers for consistent downstream consumption."""

from __future__ import annotations

from typing import Any


def _base_evidence(evidence_type: str, item: dict[str, Any], snippet_key: str = "snippet") -> dict[str, Any]:
    """Build a normalized evidence object."""
    return {
        "evidence_id": str(item.get("evidence_id") or item.get("id") or item.get("chunk_id") or ""),
        "evidence_type": evidence_type,
        "source": str(item.get("source", "")),
        "title": str(item.get("title", "")),
        "snippet": str(item.get(snippet_key) or item.get("text") or ""),
        "score": float(item.get("score", item.get("rrf_score", 0.0)) or 0.0),
        "metadata": item.get("metadata", {}),
    }


def format_trademark_evidence(item: dict[str, Any]) -> dict[str, Any]:
    """Format trademark retrieval result into standard evidence shape."""
    evidence = _base_evidence("trademark", item)
    evidence["metadata"] = {
        **(evidence.get("metadata") or {}),
        "source_type": "trademark",
        "source_table": "trademark_case / trademark_owner / trademark_class / trademark_statement",
        "serial_no": item.get("serial_no") or item.get("serial_number"),
        "mark": item.get("mark") or item.get("mark_id_char"),
        "owner": item.get("owner") or item.get("owners"),
        "intl_class": item.get("intl_class") or item.get("intl_classes") or item.get("classes"),
        "statement_snippets": item.get("statement_snippets") or item.get("statements"),
        "status": item.get("status"),
    }
    return evidence


def format_platform_policy_evidence(item: dict[str, Any]) -> dict[str, Any]:
    """Format platform policy retrieval result."""
    evidence = _base_evidence("platform_policy", item)
    evidence["metadata"] = {
        **(evidence.get("metadata") or {}),
        "platform": item.get("platform"),
        "policy_section": item.get("policy_section"),
    }
    return evidence


def format_patent_claim_evidence(item: dict[str, Any]) -> dict[str, Any]:
    """Format patent claim retrieval result."""
    evidence = _base_evidence("patent_claim", item, snippet_key="claim_text")
    evidence["metadata"] = {
        **(evidence.get("metadata") or {}),
        "patent_id": item.get("patent_id"),
        "claim_id": item.get("claim_id"),
    }
    return evidence


def format_litigation_evidence(item: dict[str, Any]) -> dict[str, Any]:
    """Format litigation retrieval result."""
    evidence = _base_evidence("litigation", item)
    evidence["metadata"] = {
        **(evidence.get("metadata") or {}),
        "case_id": item.get("case_id"),
        "court": item.get("court"),
        "filing_date": item.get("filing_date"),
    }
    return evidence


def format_evidence(evidence_type: str, item: dict[str, Any]) -> dict[str, Any]:
    """Route evidence format by evidence type."""
    mapping: dict[str, Any] = {
        "trademark": format_trademark_evidence,
        "platform_policy": format_platform_policy_evidence,
        "patent_claim": format_patent_claim_evidence,
        "litigation": format_litigation_evidence,
    }
    formatter = mapping.get(evidence_type)
    if formatter is None:
        return _base_evidence(evidence_type, item)
    return formatter(item)
