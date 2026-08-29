from pathlib import Path
from fastapi.testclient import TestClient
from legal.matter.compliance_log import ComplianceLogStore
from maine_family_law_llm import api as api_module
def rows():return [{"evidence_id":"ORDER-001","source_hash":"a"*64,"title":"Fictional order"},{"evidence_id":"EVENT-001","source_hash":"b"*64,"title":"Fictional event"}]
def terms():return [{"term_id":"term_001","exact_language":"Fictional exact order term.","source_ref":{"record_id":"ORDER-001","source_hash":"a"*64}}]
def payload():return {"log_id":"compliance_001","reviewer_safe_id":"reviewer_001","term_id":"term_001","event_id":"event_001","date_candidate":"2026-07-04","text":"Fictional observation","event_state":"observation","event_source_ref":{"record_id":"EVENT-001","source_hash":"b"*64},"user_confirmed":True}
def test_pass100_encrypted_observation_not_finding(tmp_path:Path):
 root=tmp_path/'m';root.mkdir();s=ComplianceLogStore(root,encryption_key='fictional-test-key');r=s.create(payload(),terms=terms(),records=rows());assert r['compliance']=='not_determined' and r['event']['state']=='observation';assert 'Fictional observation' not in s.path.read_text()
def test_pass100_api_scope_and_ui(monkeypatch,tmp_path:Path):
 a,b=tmp_path/'a',tmp_path/'b';a.mkdir();b.mkdir();active={'root':a};monkeypatch.setattr(api_module,'active_case_root',lambda:active['root']);monkeypatch.setattr(api_module,'load_case_search_records',lambda _:rows());monkeypatch.setattr(api_module,'_order_store',lambda:type('S',(),{'terms':lambda self:{'terms':terms()}})());monkeypatch.setenv('MAINE_MATTER_STORE_KEY','fictional-test-key');c=TestClient(api_module.app);assert c.post('/api/compliance-logs',json=payload()).status_code==200;assert len(c.get('/api/compliance-logs/compliance_001/event-source').json()['source']['source_token'])==64;active['root']=b;assert c.get('/api/compliance-logs/compliance_001').status_code==404;assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();assert 'Compliance log' in Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
