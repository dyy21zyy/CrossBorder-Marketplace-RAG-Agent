from src.evaluation.risk_eval import evaluate_risk

def test_risk_eval_runs_mock():
    out=evaluate_risk('data/eval/risk_eval.jsonl',use_reranker=False)
    assert 'metrics' in out
    assert 'overall_risk_accuracy' in out['metrics']
