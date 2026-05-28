from __future__ import annotations
import json,time
from pathlib import Path
from typing import Any
from src.retrieval.claim_retriever import ClaimRetriever
from src.retrieval.platform_retriever import PlatformPolicyRetriever

def _load_jsonl(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]

def _overlap(text, kws):
    t=text.lower(); kws=[k.lower() for k in kws]
    hit=sum(1 for k in kws if k in t)
    return hit, (hit/len(kws) if kws else 0.0)

def _eval_module(samples,module,use_reranker=False):
    rec=pre=mrr=ctx=lat=0.0; n=0
    pr=None; cr=None
    for s in samples:
        if s.get('module')!=module: continue
        n+=1; k=int(s.get('top_k',5)); q=s['query']; kws=s.get('expected_keywords',[])
        st=time.perf_counter()
        try:
            if module=='platform_policy':
                pr = pr or PlatformPolicyRetriever()
                rows=pr.hybrid_search(q,top_k=k,use_reranker=use_reranker)
            else:
                cr = cr or ClaimRetriever()
                rows=cr.hybrid_search(q,top_k=k,use_reranker=use_reranker)
        except Exception:
            rows=[]
        lat += time.perf_counter()-st
        texts=[(r.snippet if hasattr(r,'snippet') else str(r.get('text',''))) for r in rows]
        rel=[]
        for tx in texts:
            h,sc=_overlap(tx,kws); rel.append((h>0,sc)); ctx+=sc
        rec += 1.0 if any(x[0] for x in rel) else 0.0
        pre += (sum(1 for x in rel if x[0]) / max(1,k))
        rr=0.0
        for i,(ok,_) in enumerate(rel,1):
            if ok: rr=1/i; break
        mrr += rr
    if n==0:n=1
    return {'module':module,'recall_at_5':rec/n,'precision_at_5':pre/n,'mrr':mrr/n,'avg_context_relevance':ctx/(n*5),'avg_latency_sec':lat/n}

def evaluate_retrieval(path='data/eval/retrieval_eval.jsonl',compare_reranker=False):
    samples=_load_jsonl(path)
    mods=['platform_policy','patent_claim']
    base=[dict(mode='no_reranker',**_eval_module(samples,m,False)) for m in mods]
    if not compare_reranker:
        return {'no_reranker':base}
    withr=[dict(mode='with_reranker',**_eval_module(samples,m,True)) for m in mods]
    imp=[]
    for b,w in zip(base,withr,strict=False):
        imp.append({'module':b['module'],'recall_at_5_delta':w['recall_at_5']-b['recall_at_5'],'precision_at_5_delta':w['precision_at_5']-b['precision_at_5'],'mrr_delta':w['mrr']-b['mrr'],'context_relevance_delta':w['avg_context_relevance']-b['avg_context_relevance'],'latency_delta':w['avg_latency_sec']-b['avg_latency_sec']})
    return {'no_reranker':base,'with_reranker':withr,'improvement':imp}
