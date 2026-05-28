from __future__ import annotations
import argparse, os, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))
from src.evaluation.retrieval_eval import evaluate_retrieval
from src.evaluation.risk_eval import evaluate_risk
from src.evaluation.response_eval import evaluate_response
from src.evaluation.report import build_markdown_report, save_json

def parse_args():
    p=argparse.ArgumentParser()
    p.add_argument('--retrieval',action='store_true'); p.add_argument('--risk',action='store_true'); p.add_argument('--response',action='store_true'); p.add_argument('--all',action='store_true')
    p.add_argument('--compare_reranker',action='store_true'); p.add_argument('--mock_llm',default='true'); p.add_argument('--top_k',type=int,default=5); p.add_argument('--rerank_top_k',type=int,default=10); p.add_argument('--use_llm_judge',action='store_true')
    return p.parse_args()

def main():
    a=parse_args(); os.environ['MOCK_LLM']='true' if str(a.mock_llm).lower() in {'1','true','yes','y'} else 'false'
    if not any([a.retrieval,a.risk,a.response,a.all]): a.all=True
    retrieval=risk=response=None
    if a.all or a.retrieval: retrieval=evaluate_retrieval(compare_reranker=a.compare_reranker, top_k=a.top_k, rerank_top_k=a.rerank_top_k); save_json('reports/retrieval_eval_results.json',retrieval)
    if a.all or a.risk:
        no=evaluate_risk(use_reranker=False)
        risk={'no_reranker':no}
        if a.compare_reranker: risk['with_reranker']=evaluate_risk(use_reranker=True)
        save_json('reports/risk_eval_results.json',risk)
    if a.all or a.response: response=evaluate_response(); save_json('reports/response_eval_results.json',response)
    build_markdown_report(retrieval,risk,response)
    print('Evaluation finished.')
if __name__=='__main__': main()
