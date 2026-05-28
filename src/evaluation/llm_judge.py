from __future__ import annotations
from typing import Any
from src.agents.llm_client import LLMClient

def judge_response(query:str, evidence:list[dict[str,Any]], final_answer:str, llm_client:LLMClient|None=None)->dict[str,Any]:
    llm = llm_client or LLMClient()
    if llm.mock_llm or not llm.is_enabled():
        return {'skipped':True,'reason':'MOCK_LLM=true or llm disabled'}
    prompt = f"""Judge faithfulness/relevance. Return JSON only with keys faithfulness_score(1-5), answer_relevance_score(1-5), unsupported_claims(list), reason.\nQuery:{query}\nEvidence:{evidence}\nFinal answer:{final_answer}"""
    fb={'faithfulness_score':3,'answer_relevance_score':3,'unsupported_claims':[],'reason':'fallback'}
    return llm.chat_json([{'role':'system','content':'Return JSON only.'},{'role':'user','content':prompt}], fallback=fb)
