from src.evaluation.response_eval import evaluate_response

def test_response_eval_runs():
    out=evaluate_response('data/eval/response_eval.jsonl')
    assert 'metrics' in out
    assert 'faithfulness' in out['metrics']
