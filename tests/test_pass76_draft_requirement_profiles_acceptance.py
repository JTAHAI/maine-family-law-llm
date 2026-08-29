from __future__ import annotations
from pathlib import Path
from fastapi.testclient import TestClient
from legal.drafting.requirement_profiles import DraftRequirementProfileStore
from legal.documents.workspace import create_document
from maine_family_law_llm import api as api_module

def _profile() -> dict[str, object]: return {"profile_id":"profile_001","label":"Fictional local review","reviewer_safe_id":"reviewer_001","required_sections":["Background","Requested relief"],"max_characters":100,"review_gates":["Human review required"],"user_confirmed":True}
def test_pass76_stores_encrypted_local_profile_and_evaluates_only_configured_checks(tmp_path:Path)->None:
 root=tmp_path/'fictional-matter';root.mkdir();store=DraftRequirementProfileStore(root,encryption_key='fictional-test-key');profile=store.create(_profile());assert profile['filing_ready'] is False and 'court-approved' in profile['notice'];result=store.evaluate('profile_001',{'document_id':'d'*32,'current_revision_id':'e'*32,'content':'Background\nShort text'});assert result['missing_sections']==['Requested relief'] and result['review_required'] is True;assert 'Background' not in store.path.read_text(encoding='utf-8')
def test_pass76_api_is_active_matter_scoped(monkeypatch,tmp_path:Path)->None:
 a=tmp_path/'matter-a';b=tmp_path/'matter-b';a.mkdir();b.mkdir();active={'root':a};monkeypatch.setattr(api_module,'active_case_root',lambda:active['root']);monkeypatch.setenv('MAINE_MATTER_STORE_KEY','fictional-test-key');doc=create_document(a,title='Fictional profile draft',content='Background\nRequested relief',document_type='draft');client=TestClient(api_module.app);assert client.post('/api/drafting/requirement-profiles',json=_profile()).status_code==200;checked=client.post(f"/api/drafting/documents/{doc['document_id']}/requirement-profiles/profile_001/evaluate");assert checked.status_code==200 and not checked.json()['blockers'];active['root']=b;assert client.get('/api/drafting/requirement-profiles').json()['profiles']==[]
def test_pass76_ships_mirrored_production_profile_control()->None:
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();assert Path('src/maine_family_law_llm/ui/workbench.js').read_bytes()==Path('maine_family_law_llm/ui/workbench.js').read_bytes();assert 'Draft requirement profile' in Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
