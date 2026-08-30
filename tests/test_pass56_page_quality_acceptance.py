from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as a


def test_page_quality_is_metric_bound(monkeypatch,tmp_path:Path):
 r=tmp_path/'fictional';r.mkdir();monkeypatch.setattr(a,'active_case_root',lambda:r)
 monkeypatch.setattr(a,'load_case_search_records',lambda _root:[{'evidence_id':'REC-QUALITY','source_hash':'a'*64,'page_count':2,'text_excerpt':'Fictional parsed page.'}])
 c=TestClient(a.app)
 p=c.post('/api/evidence/page-quality-review',json={'source_hash':'a'*64,'pages':[{'page_number':1,'ocr_confidence':.4,'blur':True}]})
 bad=c.post('/api/evidence/page-quality-review',json={'source_hash':'bad','pages':[]})
 foreign=c.post('/api/evidence/page-quality-review',json={'source_hash':'b'*64,'pages':[]})
 outside=c.post('/api/evidence/page-quality-review',json={'source_hash':'a'*64,'pages':[{'page_number':3,'blur':True}]})
 body=p.json()
 assert p.status_code==200 and body['review_page_count']==1 and 'do not replace' in body['notice']
 assert body['source_record']=={'evidence_id':'REC-QUALITY','source_hash':'a'*64} and body['review_id'] and body['review_receipt']['history_id']
 assert bad.status_code==400 and foreign.status_code==404 and outside.status_code==400
 history=(r/'19_EVIDENCE_WORK_PRODUCT'/'review-workbench'/'evidence-review-history.jsonl').read_text(encoding='utf-8')
 assert 'page_quality_review_created' in history and 'Fictional parsed page.' not in history
def test_page_quality_ui_mirrored():
 p=Path(__file__).resolve().parents[1]
 src=(p/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
 assert src==(p/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
 assert '/api/evidence/page-quality-review' in src and 'hash-verified active-matter source' in src
 assert 'pageQualityDelegationBound' in src and 'data-specialized-source' in src
