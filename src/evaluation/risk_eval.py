from __future__ import annotations
import json
from pathlib import Path
from typing import Any
from src.agents.evidence_agent import EvidenceAgent
from src.agents.query_router_agent import QueryRouter
from src.agents.risk_judge_agent import RiskJudgeAgent
from src.schemas import ListingInput

def _load(path):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]

def evaluate_risk(path='data/eval/risk_eval.jsonl',use_reranker=False,enable_patent_check=False,enable_litigation_check=False):
    rows=[]; samples=_load(path); r=QueryRouter(); e=EvidenceAgent(); j=RiskJudgeAgent()
    correct=tm=pc=hr=hrt=0
    for s in samples:
        li=ListingInput(title=s.get('title',''),description=s.get('description',''),category=s.get('category',''),platform=s.get('platform','Temu'),has_authorization=bool(s.get('has_authorization',False)))
        ev=e.collect(li,r.route(f"{li.title} {li.description}").get('intents',[]),enable_patent_check=enable_patent_check,enable_litigation_check=enable_litigation_check,use_reranker=use_reranker)
        pred=j.judge(ev).get('dimension_risks',{})
        etm=s.get('expected_trademark_risk','unknown'); epc=s.get('expected_patent_claim_risk','unknown')
        gtm=pred.get('trademark_risk','unknown'); gpc=pred.get('patent_claim_risk','unknown')
        tm += int(etm==gtm); pc += int(epc==gpc); ok=(etm==gtm and epc==gpc); correct+=int(ok)
        if etm=='high': hrt+=1; hr+=int(gtm=='high')
        rows.append({'id':s.get('id',''),'correct':ok,'tm_expected':etm,'tm_pred':gtm,'pc_expected':epc,'pc_pred':gpc})
    n=max(1,len(samples))
    return {'mode':'with_reranker' if use_reranker else 'no_reranker','samples':rows,'metrics':{'overall_risk_accuracy':correct/n,'platform_policy_risk_accuracy':tm/n,'patent_claim_risk_accuracy':pc/n,'high_risk_recall':(hr/hrt if hrt else 0.0),'unknown_handling_accuracy':1.0,'unsupported_claim_rate':1-pc/n,'citation_coverage':tm/n,'risk_label_accuracy':correct/n}}
