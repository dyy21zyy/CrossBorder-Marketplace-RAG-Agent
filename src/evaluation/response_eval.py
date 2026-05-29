from __future__ import annotations
import json
from pathlib import Path
from typing import Any

DISCLAIMER_PATTERNS = ["preliminary ip risk screening", "does not constitute legal advice", "not legal advice"]

def _load(path:str):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]

def evaluate_response(path='data/eval/response_eval.jsonl', use_llm_judge: bool=False) -> dict[str, Any]:
    try:
        from src.agents.evidence_agent import EvidenceAgent
        from src.agents.final_answer_agent import FinalAnswerAgent
        from src.agents.query_router_agent import QueryRouter
        from src.agents.risk_judge_agent import RiskJudgeAgent
        from src.schemas import ListingInput
    except Exception as e:
        return {'per_sample':[],'metrics':{'faithfulness':0.0,'unsupported_claim_rate':1.0,'answer_relevance':0.0,'disclaimer_coverage':0.0,'forbidden_claim_rate':0.0,'citation_coverage':0.0},'warning':f'evaluation dependencies unavailable: {e}'}
    samples=_load(path); q=QueryRouter(); e=EvidenceAgent(); r=RiskJudgeAgent(); f=FinalAnswerAgent()
    per=[]
    for s in samples:
        li=ListingInput(title=s['title'],description=s.get('description',''),category=s.get('category',''),platform=s.get('platform','Temu'),has_authorization=bool(s.get('has_authorization',False)))
        ev=e.collect(li,q.route(f"{li.title} {li.description}").get('intents',[]),enable_patent_check=True,enable_litigation_check=True,use_reranker=False)
        rr=r.judge(ev)
        ans=f.generate(li,ev,rr,[]).summary.lower()
        expected=s.get('expected_answer_points',[])
        covered=sum(1 for p in expected if all(t in ans for t in p.lower().replace(' or ',' ').split()[:2]))
        answer_relevance=covered/max(1,len(expected))
        disclaimer=int(any(p in ans for p in DISCLAIMER_PATTERNS))
        forbidden=s.get('forbidden_claims',[])
        forbidden_hits=sum(1 for x in forbidden if x.lower() in ans)
        unsupported=0; claims=0
        if 'trademark' in ans: claims+=1; unsupported += int(len(ev.get('trademark_evidence',[]))==0)
        if 'patent' in ans: claims+=1; unsupported += int(len(ev.get('patent_claim_evidence',[]))==0)
        if 'litigation' in ans: claims+=1; unsupported += int(len(ev.get('litigation_evidence',[]))==0)
        if 'policy' in ans: claims+=1; unsupported += int(len(ev.get('platform_policy_evidence',[]))==0)
        unsupported_rate=unsupported/max(1,claims)
        dims=rr.get('dimension_risks',{})
        def _level(key):
            value=dims.get(key,'unknown')
            return value.get('risk_level','unknown') if isinstance(value,dict) else value
        citation_cov=sum([int(_level('trademark_risk')=='unknown' or len(ev.get('trademark_evidence',[]))>0),int(_level('patent_claim_risk')=='unknown' or len(ev.get('patent_claim_evidence',[]))>0),int(_level('litigation_risk')=='unknown' or len(ev.get('litigation_evidence',[]))>0)])/3
        per.append({'id':s['id'],'faithfulness':1-unsupported_rate,'unsupported_claim_rate':unsupported_rate,'answer_relevance':answer_relevance,'disclaimer_coverage':disclaimer,'forbidden_claim_rate':int(forbidden_hits>0),'citation_coverage':citation_cov})
    n=max(1,len(per))
    metrics={k:sum(x[k] for x in per)/n for k in ['faithfulness','unsupported_claim_rate','answer_relevance','disclaimer_coverage','forbidden_claim_rate','citation_coverage']}
    return {'per_sample':per,'metrics':metrics}
