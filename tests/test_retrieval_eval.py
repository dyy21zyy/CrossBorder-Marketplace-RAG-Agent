from src.evaluation.retrieval_eval import evaluate_retrieval

def test_retrieval_eval_mock_runs():
    out = evaluate_retrieval('data/eval/retrieval_eval.jsonl', compare_reranker=True)
    assert 'no_reranker' in out
    assert 'with_reranker' in out
