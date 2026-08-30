from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as a


def test_handwriting_review_is_routing_not_transcription(monkeypatch,tmp_path:Path):
 r=tmp_path/'fictional';r.mkdir();monkeypatch.setattr(a,'active_case_root',lambda:r)
 monkeypatch.setattr(a,'load_case_search_records',lambda _root:[{'evidence_id':'REC-HAND','source_hash':'a'*64,'title':'Fictional handwriting scan','text_content':'Fictional private test text.'}])
 c=TestClient(a.app)
 ok=c.post('/api/evidence/handwriting-review',json={'source_hash':'a'*64,'handwriting_signal':True})
 bad=c.post('/api/evidence/handwriting-review',json={'source_hash':'bad'})
 foreign=c.post('/api/evidence/handwriting-review',json={'source_hash':'b'*64,'handwriting_signal':True})
 body=ok.json()
 assert ok.status_code==200 and body['transcription_status']=='human_transcription_required' and 'does not recognize' in body['notice']
 assert body['source_record']=={'evidence_id':'REC-HAND','source_hash':'a'*64} and body['routing_id'] and body['review_receipt']['history_id']
 assert bad.status_code==400 and foreign.status_code==404
 history=(r/'19_EVIDENCE_WORK_PRODUCT'/'review-workbench'/'evidence-review-history.jsonl').read_text(encoding='utf-8')
 assert 'handwriting_review_routed' in history and 'Fictional private test text.' not in history
def test_handwriting_ui_and_api_are_mirrored():
 p=Path(__file__).resolve().parents[1]
 assert (p/'src/maine_family_law_llm/api.py').read_text(encoding='utf8')==(p/'maine_family_law_llm/api.py').read_text(encoding='utf8')
 src=(p/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
 assert src==(p/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
 assert '/api/evidence/handwriting-review' in src and 'hash-verified active-matter record' in src
 assert 'handwritingReviewDelegationBound' in src and 'data-specialized-source' in src
