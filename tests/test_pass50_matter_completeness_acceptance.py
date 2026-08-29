from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as api_module

def test_completeness_is_explainable_and_not_outcome_score(monkeypatch,tmp_path:Path):
 root=tmp_path/'fictional';root.mkdir(); rows=[{'evidence_id':'A','source_hash':'a'*64,'text':'Fictional undated record','source_type':'note','page_number':1}]
 monkeypatch.setattr(api_module,'active_case_root',lambda:root);monkeypatch.setattr(api_module,'load_case_search_records',lambda _:rows)
 p=TestClient(api_module.app).get('/api/evidence/matter-completeness');assert p.status_code==200
 body=p.json();assert body['review_required'] is True and 'do not score' in body['notice'] and 'date_review' in body['dimensions']

def test_completeness_ui_mirrors():
 root=Path(__file__).resolve().parents[1];a=(root/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8');b=(root/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8');assert a==b and '/api/evidence/matter-completeness' in a
