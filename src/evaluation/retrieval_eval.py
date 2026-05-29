from __future__ import annotations
import json, re, time
from pathlib import Path
from typing import Any


SEARCHABLE_FIELDS = (
    "text",
    "snippet",
    "page_content",
    "content",
    "source",
    "source_type",
    "metadata",
    "mark",
    "owner",
    "owners",
    "normalized_mark",
    "mark_id_char",
    "patent_id",
    "normalized_patent",
    "case_name",
    "case_number",
    "party_name",
    "party_names",
    "plaintiff_names",
    "defendant_names",
    "name",
    "name_long",
    "claim_group_text",
    "independent_claim_number",
    "dependent_claim_numbers",
    "statement_text",
    "statements",
)

TRADEMARK_FIELDS = (
    "trademark_matches",
    "mark_id_char",
    "mark",
    "normalized_mark",
    "owner",
    "owners",
    "statement",
    "statement_text",
    "statements",
    "term",
    "metadata",
    "snippet",
)
PATENT_FIELDS = ("claim_group_text", "snippet", "metadata", "patent_id", "text")
LITIGATION_FIELDS = (
    "patent_id",
    "patent",
    "normalized_patent",
    "case_number",
    "case_name",
    "party_name",
    "party_names",
    "plaintiff_names",
    "defendant_names",
    "plaintiff",
    "defendant",
    "name",
    "name_long",
    "metadata",
    "snippet",
)


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"retrieval eval dataset not found: {path}")
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _to_mapping(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    if hasattr(value, "dict"):
        return value.dict()
    return None


def _flatten_to_strings(value: Any) -> list[str]:
    """Recursively flatten evidence values into strings for keyword matching."""
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (int, float, bool)):
        return [str(value)]
    mapping = _to_mapping(value)
    if mapping is not None:
        parts: list[str] = []
        for key, val in mapping.items():
            parts.append(str(key))
            parts.extend(_flatten_to_strings(val))
        return parts
    if isinstance(value, (list, tuple, set)):
        parts = []
        for item in value:
            parts.extend(_flatten_to_strings(item))
        return parts
    return [str(value)]


def _field_value(evidence: Any, field: str) -> Any:
    mapping = _to_mapping(evidence)
    if mapping is not None:
        return mapping.get(field)
    return getattr(evidence, field, None)


def _field_text(evidence: Any, fields: tuple[str, ...]) -> str:
    parts: list[str] = []
    for field in fields:
        parts.extend(_flatten_to_strings(_field_value(evidence, field)))
    return " ".join(parts).lower()


def evidence_to_searchable_text(evidence: Any) -> str:
    """Build lower-case searchable text from all evidence fields used in eval."""
    parts: list[str] = []
    for field in SEARCHABLE_FIELDS:
        parts.extend(_flatten_to_strings(_field_value(evidence, field)))
    # Include the whole object as a fallback so direct dict evidence with
    # adjacent fields (for example plaintiff_names/defendant_names) remains searchable.
    parts.extend(_flatten_to_strings(evidence))
    return " ".join(part for part in parts if part).lower()




def _evidence_preview(evidence: Any, limit: int = 240) -> str:
    text = evidence_to_searchable_text(evidence)
    compact = " ".join(text.split())
    return compact[:limit]


def _has_reranker_score(evidence: Any) -> bool:
    mapping = _to_mapping(evidence)
    if mapping is not None:
        if mapping.get("reranker_score") is not None:
            return True
        metadata = mapping.get("metadata")
        return isinstance(metadata, dict) and metadata.get("reranker_score") is not None
    if getattr(evidence, "reranker_score", None) is not None:
        return True
    metadata = getattr(evidence, "metadata", None)
    return isinstance(metadata, dict) and metadata.get("reranker_score") is not None


def _score_summary(evidence: Any) -> dict[str, Any]:
    mapping = _to_mapping(evidence) or {}
    metadata = mapping.get("metadata") if isinstance(mapping, dict) else None
    metadata = metadata if isinstance(metadata, dict) else {}
    return {
        "score": mapping.get("score"),
        "rrf_score": mapping.get("rrf_score", metadata.get("rrf_score")),
        "reranker_score": mapping.get("reranker_score", metadata.get("reranker_score")),
        "retrieval_method": mapping.get("retrieval_method", metadata.get("retrieval_method")),
    }

# Backward-compatible alias for older callers/tests.
def _textify(row: Any) -> str:
    return evidence_to_searchable_text(row)


def _keyword_hits(text: str, expected_keywords: list[str]) -> list[str]:
    hits = []
    for kw in expected_keywords:
        normalized = str(kw).strip().lower()
        if normalized and normalized in text:
            hits.append(normalized)
    return hits


def _tokens(text: str) -> set[str]:
    stopwords = {"a", "an", "and", "by", "for", "history", "in", "of", "or", "patent", "the", "to", "with", "temu"}
    return {tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if len(tok) > 1 and tok not in stopwords}


def _eval_evidence_relevance(module: str, evidence: Any, expected_keywords: list[str], query: str) -> dict[str, Any]:
    searchable_text = evidence_to_searchable_text(evidence)
    matched_keywords = set(_keyword_hits(searchable_text, expected_keywords))
    relevant = False
    keyword_coverage = len(matched_keywords) / max(1, len(expected_keywords))
    context_relevance = keyword_coverage
    rule_based_hit = False

    if module == "platform_policy":
        query_overlap = _tokens(query).intersection(_tokens(searchable_text))
        relevant = bool(matched_keywords) or bool(query_overlap)
        context_relevance = max(keyword_coverage, len(query_overlap) / max(1, len(_tokens(query))))

    elif module == "patent_claim":
        patent_text = _field_text(evidence, PATENT_FIELDS) or searchable_text
        matched_keywords = set(_keyword_hits(patent_text, expected_keywords))
        product_overlap = _tokens(query).intersection(_tokens(patent_text))
        relevant = bool(matched_keywords) or len(product_overlap) >= 2
        keyword_coverage = len(matched_keywords) / max(1, len(expected_keywords))
        context_relevance = max(keyword_coverage, len(product_overlap) / max(1, len(_tokens(query))))

    elif module == "trademark":
        trademark_text = _field_text(evidence, TRADEMARK_FIELDS) or searchable_text
        brand_keywords = [kw for kw in expected_keywords if str(kw).strip().lower() not in {"owner", "owners"}]
        matched_keywords = set(_keyword_hits(trademark_text, brand_keywords))
        rule_based_hit = any(marker in trademark_text for marker in ("risk_screening", "potential risk", "direct trademark", "trademark_case")) and bool(matched_keywords)
        relevant = bool(matched_keywords) or rule_based_hit
        keyword_coverage = len(matched_keywords) / max(1, len(brand_keywords))
        context_relevance = keyword_coverage

    elif module == "litigation":
        litigation_text = _field_text(evidence, LITIGATION_FIELDS)
        has_litigation_evidence = bool(litigation_text.strip()) or "litigation" in searchable_text or "case_count" in searchable_text
        matched_keywords = set(_keyword_hits(searchable_text, expected_keywords))
        relevant = has_litigation_evidence and bool(matched_keywords)
        keyword_coverage = len(matched_keywords) / max(1, len(expected_keywords))
        context_relevance = keyword_coverage

    else:
        relevant = bool(matched_keywords)

    return {
        "relevant": relevant,
        "matched_keywords": sorted(matched_keywords),
        "keyword_coverage": keyword_coverage,
        "context_relevance": context_relevance,
        "rule_based_hit": rule_based_hit,
        "searchable_text": searchable_text,
    }


def _eval_single_query(results: list[Any], expected_keywords: list[str], k: int, module: str = "", query: str = "") -> dict[str, Any]:
    relevance: list[bool] = []
    matched: set[str] = set()
    context_scores: list[float] = []
    keyword_scores: list[float] = []
    rule_based_hit = False

    for r in results[:k]:
        eval_row = _eval_evidence_relevance(module, r, expected_keywords, query)
        relevance.append(bool(eval_row["relevant"]))
        matched.update(eval_row["matched_keywords"])
        context_scores.append(float(eval_row["context_relevance"]))
        keyword_scores.append(float(eval_row["keyword_coverage"]))
        rule_based_hit = rule_based_hit or bool(eval_row["rule_based_hit"])

    rel_count = sum(1 for x in relevance if x)
    precision = rel_count / max(1, k)
    recall = 1.0 if rel_count > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    mrr = 0.0
    ap_acc = 0.0
    seen_rel = 0
    for i, is_rel in enumerate(relevance, start=1):
        if is_rel:
            seen_rel += 1
            if mrr == 0.0:
                mrr = 1 / i
            ap_acc += seen_rel / i
    ap = ap_acc / max(1, rel_count)
    context_rel = max(context_scores, default=0.0)
    keyword_coverage = max(keyword_scores, default=0.0)
    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "f1_at_k": f1,
        "mrr": mrr,
        "ap_at_k": ap,
        "context_relevance": context_rel,
        "keyword_coverage": keyword_coverage,
        "matched_keywords": sorted(matched),
        "relevant": bool(rel_count),
        "rule_based_hit": rule_based_hit,
    }


def _retrieve(module: str, query: str, k: int, use_reranker: bool, rerank_top_k: int) -> list[Any]:
    if module == "platform_policy":
        from src.retrieval.platform_retriever import PlatformPolicyRetriever
        retriever = PlatformPolicyRetriever()
        retriever.rerank_top_k = rerank_top_k
        return retriever.hybrid_search(query, top_k=k, use_reranker=use_reranker, rerank_top_k=rerank_top_k)
    if module == "patent_claim":
        from src.retrieval.claim_retriever import ClaimRetriever
        retriever = ClaimRetriever()
        retriever.rerank_top_k = rerank_top_k
        return retriever.hybrid_search(query, top_k=k, use_reranker=use_reranker, rerank_top_k=rerank_top_k)
    if module == "trademark":
        from src.retrieval.trademark_retriever import TrademarkRetriever
        matches = TrademarkRetriever().search_trademarks(type("obj", (), {"candidate_brand_terms": query.split(), "brand_terms": query.split(), "normalized_title": query, "normalized_description": ""})())
        return [m.evidence if getattr(m, "evidence", None) is not None else m for m in matches]
    if module == "litigation":
        from src.retrieval.litigation_retriever import LitigationRetriever
        token = "".join(ch for ch in query if ch.isdigit())
        if not token:
            return []
        retriever = LitigationRetriever()
        summary = retriever.get_litigation_summary(token)
        if summary:
            return [summary]
        return retriever.get_litigation_by_patent(token)[:k]
    raise ValueError(f"unsupported module: {module}")


def evaluate_retrieval(path: str = "data/eval/retrieval_eval.jsonl", compare_reranker: bool = False, top_k: int = 5, rerank_top_k: int = 10) -> dict[str, Any]:
    samples = _load_jsonl(path)

    def run(use_reranker: bool) -> dict[str, Any]:
        per_query = []
        for s in samples:
            module = s["module"]
            k = int(s.get("top_k", top_k))
            should_rerank = use_reranker and module in {"platform_policy", "patent_claim"}
            st = time.perf_counter()
            warning = None
            try:
                results = _retrieve(module, s["query"], k, should_rerank, rerank_top_k)
            except Exception as e:
                results = []
                warning = str(e)
            latency = time.perf_counter() - st
            if should_rerank and results and not any(_has_reranker_score(r) for r in results):
                missing_score_warning = "with_reranker result has no reranker_score; CrossEncoder likely fell back or was unavailable"
                warning = f"{warning}; {missing_score_warning}" if warning else missing_score_warning
            expected_keywords = s.get("expected_keywords", [])
            metrics = _eval_single_query(results, expected_keywords, k, module=module, query=s["query"])
            top_evidence = results[0] if results else None
            per_query.append({
                "id": s["id"],
                "module": module,
                "query": s["query"],
                "expected_keywords": expected_keywords,
                "retrieved_evidence_count": len(results),
                "top_evidence_preview": _evidence_preview(top_evidence) if top_evidence else "",
                "top_evidence_scores": _score_summary(top_evidence) if top_evidence else {},
                "matched_keywords": metrics.pop("matched_keywords"),
                "relevant": metrics.pop("relevant"),
                "latency_sec": latency,
                "warning": warning,
                **metrics,
            })

        by_module: dict[str, list[dict[str, Any]]] = {}
        for row in per_query:
            by_module.setdefault(row["module"], []).append(row)
        module_metrics = []
        for module, rows in by_module.items():
            n = len(rows)
            agg = {key: sum(r[key] for r in rows) / max(1, n) for key in ["precision_at_k", "recall_at_k", "f1_at_k", "mrr", "ap_at_k", "context_relevance", "latency_sec"]}
            warnings = [r["warning"] for r in rows if r.get("warning")]
            module_metrics.append({"module": module, "precision_at_k": agg["precision_at_k"], "recall_at_k": agg["recall_at_k"], "f1_at_k": agg["f1_at_k"], "map": agg["ap_at_k"], "mrr": agg["mrr"], "context_relevance": agg["context_relevance"], "avg_latency_sec": agg["latency_sec"], "warnings": warnings})
        n_all = len(per_query)
        overall = {key: sum(r[key] for r in per_query) / max(1, n_all) for key in ["precision_at_k", "recall_at_k", "f1_at_k", "mrr", "ap_at_k", "context_relevance", "latency_sec"]}
        return {"per_query": per_query, "by_module": module_metrics, "overall": {"module": "overall", "precision_at_k": overall["precision_at_k"], "recall_at_k": overall["recall_at_k"], "f1_at_k": overall["f1_at_k"], "map": overall["ap_at_k"], "mrr": overall["mrr"], "context_relevance": overall["context_relevance"], "avg_latency_sec": overall["latency_sec"]}}

    no_res = run(False)
    out = {"no_reranker": no_res}
    if compare_reranker:
        with_res = run(True)
        out["with_reranker"] = with_res
        deltas = []
        for module in ["platform_policy", "patent_claim"]:
            b = next((x for x in no_res["by_module"] if x["module"] == module), None)
            w = next((x for x in with_res["by_module"] if x["module"] == module), None)
            if b and w:
                no_row = next((r for r in no_res["per_query"] if r["module"] == module), {})
                with_row = next((r for r in with_res["per_query"] if r["module"] == module), {})
                deltas.append({
                    "module": module,
                    f"recall_at_{top_k}_no_reranker": b["recall_at_k"],
                    f"recall_at_{top_k}_with_reranker": w["recall_at_k"],
                    f"recall_at_{top_k}_delta": w["recall_at_k"] - b["recall_at_k"],
                    f"precision_at_{top_k}_delta": w["precision_at_k"] - b["precision_at_k"],
                    "mrr_delta": w["mrr"] - b["mrr"],
                    "no_reranker_latency_sec": b["avg_latency_sec"],
                    "with_reranker_latency_sec": w["avg_latency_sec"],
                    "latency_delta": w["avg_latency_sec"] - b["avg_latency_sec"],
                    "no_reranker_top_evidence_preview": no_row.get("top_evidence_preview", ""),
                    "with_reranker_top_evidence_preview": with_row.get("top_evidence_preview", ""),
                    "with_reranker_top_evidence_scores": with_row.get("top_evidence_scores", {}),
                    "warnings": w.get("warnings", []),
                })
        out["reranker_ablation"] = deltas
    return out
