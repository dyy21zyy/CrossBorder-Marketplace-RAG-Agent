from __future__ import annotations
import json
from pathlib import Path
from typing import Any
RISK_FIELDS=[('trademark_risk','expected_trademark_risk'),('platform_policy_risk','expected_platform_policy_risk'),('patent_claim_risk','expected_patent_claim_risk'),('litigation_risk','expected_litigation_risk')]

def _load(path:str):
    return [json.loads(x) for x in Path(path).read_text(encoding='utf-8').splitlines() if x.strip()]

def _score(rows, dim):
    n=len(rows)
    acc=sum(1 for r in rows if r['pred'][dim]==r['exp'][dim])/max(1,n)
    high=[r for r in rows if r['exp'][dim]=='high']
    hr=sum(1 for r in high if r['pred'][dim] in {'high','medium'})/max(1,len(high))
    unk=[r for r in rows if r['exp'][dim]=='unknown']
    unk_acc=sum(1 for r in unk if r['pred'][dim] != 'high')/max(1,len(unk))
    fp_den=[r for r in rows if r['exp'][dim] in {'low','unknown'}]
    fp=sum(1 for r in fp_den if r['pred'][dim]=='high')/max(1,len(fp_den))
    fn_den=[r for r in rows if r['exp'][dim]=='high']
    fn=sum(1 for r in fn_den if r['pred'][dim] in {'low','unknown'})/max(1,len(fn_den))
    return acc,hr,unk_acc,fp,fn

def evaluate_risk(path='data/eval/risk_eval.jsonl',use_reranker=False):
    try:
        from src.agents.evidence_agent import EvidenceAgent
        from src.agents.query_router_agent import QueryRouter
        from src.agents.risk_judge_agent import RiskJudgeAgent
        from src.schemas import ListingInput
    except Exception as e:
        return {'mode':'with_reranker' if use_reranker else 'no_reranker','per_sample':[],'metrics':{'overall_risk_accuracy':0.0},'warning':f'evaluation dependencies unavailable: {e}'}
    samples=_load(path); q=QueryRouter(); e=EvidenceAgent(); j=RiskJudgeAgent(); rows=[]
    for s in samples:
        li=ListingInput(title=s['title'],description=s.get('description',''),category=s.get('category',''),platform=s.get('platform','Temu'),has_authorization=bool(s.get('has_authorization',False)))
        ev=e.collect(li,q.route(f"{li.title} {li.description}").get('intents',[]),enable_patent_check=bool(s.get('enable_patent_check',False)),enable_litigation_check=bool(s.get('enable_litigation_check',False)),use_reranker=use_reranker)
        pred=j.judge(ev)
        exp={d:s.get(ed,'unknown') for d,ed in RISK_FIELDS}; got=pred.get('dimension_risks',{})
        def _level(key):
            value=got.get(key,'unknown')
            return value.get('risk_level','unknown') if isinstance(value,dict) else value
        rows.append({'id':s['id'],'exp':exp,'pred':{d:_level(d) for d,_ in RISK_FIELDS},'overall_expected':s.get('expected_overall_risk','unknown'),'overall_pred':pred.get('overall_risk','unknown')})
    metrics={}
    for dim,_ in RISK_FIELDS:
        acc,hr,ua,fp,fn=_score(rows,dim)
        metrics[f'{dim}_accuracy']=acc; metrics[f'{dim}_high_risk_recall']=hr; metrics[f'{dim}_unknown_handling_accuracy']=ua; metrics[f'{dim}_false_positive_rate']=fp; metrics[f'{dim}_false_negative_rate']=fn
    metrics['overall_risk_accuracy']=sum(1 for r in rows if r['overall_expected']==r['overall_pred'])/max(1,len(rows))
    return {'mode':'with_reranker' if use_reranker else 'no_reranker','per_sample':rows,'metrics':metrics}
