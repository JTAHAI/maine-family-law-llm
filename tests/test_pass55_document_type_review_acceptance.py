from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as a


def test_document_type_review_is_explainable(monkeypatch,tmp_path:Path):
 r=tmp_path/'fictional';r.mkdir();monkeypatch.setattr(a,'active_case_root',lambda:r)
 monkeypatch.setattr(a,'load_case_search_records',lambda _root:[{'evidence_id':'REC-TYPE','source_hash':'a'*64,'title':'Fictional affidavit','text_excerpt':'Fictional affidavit sworn statement only.'}])
 c=TestClient(a.app)
 ok=c.post('/api/evidence/document-type-review',json={'source_hash':'a'*64,'text_excerpt':'Affidavit sworn statement'})
 bad=c.post('/api/evidence/document-type-review',json={'source_hash':'bad'})
 foreign=c.post('/api/evidence/document-type-review',json={'source_hash':'b'*64,'text_excerpt':'Affidavit'})
 unrelated=c.post('/api/evidence/document-type-review',json={'source_hash':'a'*64,'text_excerpt':'Invented unrelated text'})
 body=ok.json()
 assert ok.status_code==200 and 'affidavit' in body['candidate_types'] and body['review_required']
 assert body['source_record']=={'evidence_id':'REC-TYPE','source_hash':'a'*64} and body['review_id'] and body['review_receipt']['history_id']
 assert bad.status_code==400 and foreign.status_code==404 and unrelated.status_code==400
 history=(r/'19_EVIDENCE_WORK_PRODUCT'/'review-workbench'/'evidence-review-history.jsonl').read_text(encoding='utf-8')
 assert 'document_type_review_created' in history and 'Fictional affidavit sworn statement only.' not in history
def test_document_type_ui_is_mirrored():
 p=Path(__file__).resolve().parents[1]
 src=(p/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
 assert src==(p/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
 assert '/api/evidence/document-type-review' in src and 'hash-verified active-matter record' in src
 assert 'documentTypeReviewDelegationBound' in src and 'data-specialized-source' in src
