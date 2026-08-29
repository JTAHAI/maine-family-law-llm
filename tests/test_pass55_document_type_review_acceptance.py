from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as a
def test_document_type_review_is_explainable(monkeypatch,tmp_path:Path):
 r=tmp_path/'fictional';r.mkdir();monkeypatch.setattr(a,'active_case_root',lambda:r);c=TestClient(a.app);ok=c.post('/api/evidence/document-type-review',json={'source_hash':'a'*64,'text_excerpt':'Affidavit sworn statement'});bad=c.post('/api/evidence/document-type-review',json={'source_hash':'bad'});assert ok.status_code==200 and 'affidavit' in ok.json()['candidate_types'] and ok.json()['review_required'];assert bad.status_code==400
def test_document_type_ui_is_mirrored():
 p=Path(__file__).resolve().parents[1];assert (p/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')==(p/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
