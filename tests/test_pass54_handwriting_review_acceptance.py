from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as a
def test_handwriting_review_is_routing_not_transcription(monkeypatch,tmp_path:Path):
 r=tmp_path/'fictional';r.mkdir();monkeypatch.setattr(a,'active_case_root',lambda:r);c=TestClient(a.app);ok=c.post('/api/evidence/handwriting-review',json={'source_hash':'a'*64,'handwriting_signal':True});bad=c.post('/api/evidence/handwriting-review',json={'source_hash':'bad'});assert ok.status_code==200 and ok.json()['transcription_status']=='human_transcription_required' and 'does not recognize' in ok.json()['notice'];assert bad.status_code==400
def test_handwriting_ui_and_api_are_mirrored():
 p=Path(__file__).resolve().parents[1];assert (p/'src/maine_family_law_llm/api.py').read_text(encoding='utf8')==(p/'maine_family_law_llm/api.py').read_text(encoding='utf8');assert (p/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')==(p/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf8')
