from __future__ import annotations
import json, time
from pathlib import Path
from typing import Any


def _load_jsonl(path: str) -> list[dict[str, Any]]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"retrieval eval dataset not found: {path}")
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]


def _textify(row: Any) -> str:
    if hasattr(row, "snippet"):
        return f"{getattr(row, 'snippet', '')} {getattr(row, 'title', '')} {getattr(row, 'source', '')} {getattr(row, 'metadata', {})}"
    if isinstance(row, dict):
        return f"{row.get('text','')} {row.get('snippet','')} {row.get('title','')} {row.get('metadata',{})}"
    return str(row)


def _eval_single_query(results: list[Any], expected_keywords: list[str], k: int) -> dict[str, float]:
    kws = [x.lower() for x in expected_keywords]
    relevance = []
    matched = set()
    for r in results[:k]:
        txt = _textify(r).lower()
        hits = [kw for kw in kws if kw in txt]
        for h in hits:
            matched.add(h)
        relevance.append(bool(hits))
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
    context_rel = len(matched) / max(1, len(kws))
    return {
        "precision_at_k": precision,
        "recall_at_k": recall,
        "f1_at_k": f1,
        "mrr": mrr,
        "ap_at_k": ap,
        "context_relevance": context_rel,
    }


def _retrieve(module: str, query: str, k: int, use_reranker: bool, rerank_top_k: int) -> list[Any]:
    if module == "platform_policy":
        from src.retrieval.platform_retriever import PlatformPolicyRetriever
        return PlatformPolicyRetriever().hybrid_search(query, top_k=k, use_reranker=use_reranker, rerank_top_k=rerank_top_k)
    if module == "patent_claim":
        from src.retrieval.claim_retriever import ClaimRetriever
        return ClaimRetriever().hybrid_search(query, top_k=k, use_reranker=use_reranker, rerank_top_k=rerank_top_k)
    if module == "trademark":
        from src.retrieval.trademark_retriever import TrademarkRetriever
        matches = TrademarkRetriever().search_trademarks(type("obj", (), {"candidate_brand_terms": query.split(), "brand_terms": query.split(), "normalized_title": query, "normalized_description": ""})())
        return [m.evidence for m in matches if getattr(m, "evidence", None)]
    if module == "litigation":
        from src.retrieval.litigation_retriever import LitigationRetriever
        token = "".join(ch for ch in query if ch.isdigit())
        if not token:
            return []
        summary = LitigationRetriever().get_litigation_summary(token)
        return [summary] if summary else []
    raise ValueError(f"unsupported module: {module}")


def evaluate_retrieval(path: str = "data/eval/retrieval_eval.jsonl", compare_reranker: bool = False, top_k: int = 5, rerank_top_k: int = 10) -> dict[str, Any]:
    samples = _load_jsonl(path)

    def run(use_reranker: bool) -> dict[str, Any]:
        per_query = []
        for s in samples:
            module = s["module"]
            k = int(s.get("top_k", top_k))
            st = time.perf_counter()
            warning = None
            try:
                results = _retrieve(module, s["query"], k, use_reranker and module in {"platform_policy", "patent_claim"}, rerank_top_k)
            except Exception as e:
                results = []
                warning = str(e)
            latency = time.perf_counter() - st
            metrics = _eval_single_query(results, s.get("expected_keywords", []), k)
            per_query.append({"id": s["id"], "module": module, "latency_sec": latency, "warning": warning, **metrics})

        by_module: dict[str, list[dict[str, Any]]] = {}
        for row in per_query:
            by_module.setdefault(row["module"], []).append(row)
        module_metrics = []
        for module, rows in by_module.items():
            n = len(rows)
            agg = {k: sum(r[k] for r in rows) / max(1, n) for k in ["precision_at_k", "recall_at_k", "f1_at_k", "mrr", "ap_at_k", "context_relevance", "latency_sec"]}
            module_metrics.append({"module": module, "precision_at_k": agg["precision_at_k"], "recall_at_k": agg["recall_at_k"], "f1_at_k": agg["f1_at_k"], "map": agg["ap_at_k"], "mrr": agg["mrr"], "context_relevance": agg["context_relevance"], "avg_latency_sec": agg["latency_sec"]})
        n_all = len(per_query)
        overall = {k: sum(r[k] for r in per_query) / max(1, n_all) for k in ["precision_at_k", "recall_at_k", "f1_at_k", "mrr", "ap_at_k", "context_relevance", "latency_sec"]}
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
                deltas.append({"module": module, f"recall_at_{top_k}_no_reranker": b["recall_at_k"], f"recall_at_{top_k}_with_reranker": w["recall_at_k"], f"recall_at_{top_k}_delta": w["recall_at_k"] - b["recall_at_k"], f"precision_at_{top_k}_delta": w["precision_at_k"] - b["precision_at_k"], "mrr_delta": w["mrr"] - b["mrr"], "latency_delta": w["avg_latency_sec"] - b["avg_latency_sec"]})
        out["reranker_ablation"] = deltas
    return out
