from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.report import build_markdown_report, save_json
from src.evaluation.response_eval import evaluate_response
from src.evaluation.retrieval_eval import evaluate_retrieval
from src.evaluation.risk_eval import evaluate_risk


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument("--retrieval", action="store_true")
    p.add_argument("--risk", action="store_true")
    p.add_argument("--response", action="store_true")
    p.add_argument("--all", action="store_true")
    p.add_argument("--compare_reranker", action="store_true")
    p.add_argument("--mock_llm", default="true")
    p.add_argument("--top_k", type=int, default=5)
    p.add_argument("--rerank_top_k", type=int, default=10)
    p.add_argument("--use_llm_judge", action="store_true")
    p.add_argument(
        "--zh",
        action="store_true",
        help="Use Chinese risk/response evaluation datasets.",
    )
    return p.parse_args()


def main():
    a = parse_args()
    os.environ["MOCK_LLM"] = (
        "true" if str(a.mock_llm).lower() in {"1", "true", "yes", "y"} else "false"
    )
    if not any([a.retrieval, a.risk, a.response, a.all]):
        a.all = True

    risk_path = "data/eval/risk_eval_zh.jsonl" if a.zh else "data/eval/risk_eval.jsonl"
    response_path = (
        "data/eval/response_eval_zh.jsonl" if a.zh else "data/eval/response_eval.jsonl"
    )

    retrieval = risk = response = None
    if a.all or a.retrieval:
        retrieval = evaluate_retrieval(
            compare_reranker=a.compare_reranker,
            top_k=a.top_k,
            rerank_top_k=a.rerank_top_k,
        )
        save_json("reports/retrieval_eval_results.json", retrieval)
    if a.all or a.risk:
        no = evaluate_risk(path=risk_path, use_reranker=False)
        risk = {"no_reranker": no, "dataset": risk_path}
        if a.compare_reranker:
            risk["with_reranker"] = evaluate_risk(path=risk_path, use_reranker=True)
        save_json("reports/risk_eval_results.json", risk)
    if a.all or a.response:
        response = evaluate_response(path=response_path, use_llm_judge=a.use_llm_judge)
        response["dataset"] = response_path
        save_json("reports/response_eval_results.json", response)
    build_markdown_report(retrieval, risk, response)
    print("Evaluation finished.")


if __name__ == "__main__":
    main()
