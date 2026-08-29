from pathlib import Path
from fastapi.testclient import TestClient
from legal.matter.communication_plan import CommunicationPlanStore
from maine_family_law_llm import api as api_module
def rows():return [{"evidence_id":"MESSAGE-001","source_hash":"a"*64,"title":"Fictional communication"}]
def payload():return {"plan_id":"communication_001","reviewer_safe_id":"reviewer_001","user_confirmed":True,"terms":[{"term_id":"term_001","topic":"exchange","text":"Fictional neutral exchange term"}],"source_refs":[{"record_id":"MESSAGE-001","source_hash":"a"*64}]}
def test_pass99_encrypted_neutral_plan(tmp_path:Path):
 root=tmp_path/'m';root.mkdir();s=CommunicationPlanStore(root,encryption_key='fictional-test-key');r=s.create(payload(),records=rows());assert r['agreement_status']=='not_determined' and r['safety_status']=='not_determined';assert s.source('communication_001','MESSAGE-001')['source']['source_hash']=='a'*64;assert 'neutral exchange' not in s.path.read_text()
def test_pass99_api_scope_source_and_ui(monkeypatch,tmp_path:Path):
 a,b=tmp_path/'a',tmp_path/'b';a.mkdir();b.mkdir();active={'root':a};monkeypatch.setattr(api_module,'active_case_root',lambda:active['root']);monkeypatch.setattr(api_module,'load_case_search_records',lambda _:rows());monkeypatch.setenv('MAINE_MATTER_STORE_KEY','fictional-test-key');c=TestClient(api_module.app);assert c.post('/api/communication-plans',json=payload()).status_code==200;assert len(c.get('/api/communication-plans/communication_001/sources/MESSAGE-001').json()['source']['source_token'])==64;active['root']=b;assert c.get('/api/communication-plans/communication_001').status_code==404;assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();assert 'Communication plan' in Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
