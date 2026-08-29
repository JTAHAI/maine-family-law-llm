from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as a
def test_page_quality_is_metric_bound(monkeypatch,tmp_path:Path):
 r=tmp_path/'fictional';r.mkdir();monkeypatch.setattr(a,'active_case_root',lambda:r);p=TestClient(a.app).post('/api/evidence/page-quality-review',json={'source_hash':'a'*64,'pages':[{'page_number':1,'ocr_confidence':.4,'blur':True}]});assert p.status_code==200 and p.json()['review_page_count']==1 and 'do not replace' in p.json()['notice']
def test_page_quality_ui_mirrored():
 p=Path(__file__).resolve().parents[1];assert (p/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')==(p/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
