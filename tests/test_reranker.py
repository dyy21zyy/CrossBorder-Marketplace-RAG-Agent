from src.retrieval.reranker import CrossEncoderReranker

def test_reranker_disabled_no_model_load():
    rr = CrossEncoderReranker(use_reranker=False)
    out = rr.rerank('q',[{'text':'abc','rrf_score':1.0}],top_k=1)
    assert len(out)==1

def test_reranker_fallback_when_model_unavailable():
    rr = CrossEncoderReranker(model_name='invalid/model', use_reranker=True)
    out = rr.rerank('q',[{'text':'abc','rrf_score':1.0}],top_k=1)
    assert len(out)==1
