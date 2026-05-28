from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.evaluation.report import build_markdown_report
from src.evaluation.retrieval_eval import evaluate_retrieval
from src.evaluation.risk_eval import evaluate_risk


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run retrieval + risk evaluation")
    p.add_argument("--mock_llm", default="true")
    p.add_argument("--enable_patent_check", action="store_true")
    p.add_argument("--enable_litigation_check", action="store_true")
    p.add_argument("--retrieval_eval_path", default="data/eval/retrieval_eval.jsonl")
    p.add_argument("--risk_eval_path", default="data/eval/risk_eval.jsonl")
    return p.parse_args()


def _to_bool(v: str) -> bool:
    return str(v).strip().lower() in {"1", "true", "yes", "y"}


def main() -> None:
    args = parse_args()
    os.environ["MOCK_LLM"] = "true" if _to_bool(args.mock_llm) else "false"

    risk_path = args.risk_eval_path
    if not Path(risk_path).exists():
        risk_path = "data/eval/listing_risk_examples.jsonl"

    retrieval = evaluate_retrieval(args.retrieval_eval_path)
    risk = evaluate_risk(risk_path, enable_patent_check=args.enable_patent_check, enable_litigation_check=args.enable_litigation_check)
    build_markdown_report(retrieval, risk, out_path="reports/evaluation_report.md")

    print("Evaluation finished.")
    print(f"Retrieval metrics: {retrieval['metrics']}")
    print(f"Risk metrics: {risk['metrics']}")
    print("Report written to reports/evaluation_report.md")


if __name__ == "__main__":
    main()
