from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as a


def test_scanner_review_api_and_ui(monkeypatch,tmp_path:Path):
 root=tmp_path/'fictional';root.mkdir();monkeypatch.setattr(a,'active_case_root',lambda:root)
 monkeypatch.setattr(a,'load_case_search_records',lambda _root:[{'evidence_id':'REC-SCAN','source_hash':'a'*64,'title':'Fictional scan','text_content':'Fictional scan only.'}])
 c=TestClient(a.app)
 ok=c.post('/api/evidence/scanner-review/plan',json={'original_sha256':'a'*64,'page_count':2,'duplex':True,'blank_pages':[2],'rotations':{'1':90}})
 bad=c.post('/api/evidence/scanner-review/plan',json={'original_sha256':'bad','page_count':2})
 foreign=c.post('/api/evidence/scanner-review/plan',json={'original_sha256':'b'*64,'page_count':2})
 body=ok.json()
 assert ok.status_code==200 and body['profile']['blank_page_candidates']==[2] and body['review_required']
 assert body['source_record']=={'evidence_id':'REC-SCAN','source_hash':'a'*64} and body['review_receipt']['history_id']
 assert bad.status_code==400 and foreign.status_code==404
 history=(root/'19_EVIDENCE_WORK_PRODUCT'/'review-workbench'/'evidence-review-history.jsonl').read_text(encoding='utf-8')
 assert 'scanner_review_plan_created' in history and 'Fictional scan only.' not in history
 p=Path(__file__).resolve().parents[1];src=(p/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
 assert src==(p/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8') and '/api/evidence/scanner-review/plan' in src and 'No page is deleted' in src
 assert 'scannerReviewDelegationBound' in src and 'data-specialized-source' in src
 assert "const safeId=String(recordId||'').trim();" in src
 assert 'A-Za-z0-9._-' in src
