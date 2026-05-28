from src.evaluation.report import build_markdown_report

def test_eval_report_writes(tmp_path):
    p=tmp_path/'report.md'
    txt=build_markdown_report({'no_reranker':{'by_module':[]}}, {'metrics':{}}, {'metrics':{}}, str(p))
    assert p.exists()
    assert 'Evaluation Report' in txt
