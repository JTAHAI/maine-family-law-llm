from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as a
def test_scanner_review_api_and_ui(monkeypatch,tmp_path:Path):
 root=tmp_path/'fictional';root.mkdir();monkeypatch.setattr(a,'active_case_root',lambda:root);c=TestClient(a.app)
 ok=c.post('/api/evidence/scanner-review/plan',json={'original_sha256':'a'*64,'page_count':2,'duplex':True,'blank_pages':[2],'rotations':{'1':90}});bad=c.post('/api/evidence/scanner-review/plan',json={'original_sha256':'bad','page_count':2})
 assert ok.status_code==200 and ok.json()['profile']['blank_page_candidates']==[2] and ok.json()['review_required'];assert bad.status_code==400
 p=Path(__file__).resolve().parents[1];src=(p/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8');assert src==(p/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8') and '/api/evidence/scanner-review/plan' in src and 'No page is deleted' in src
