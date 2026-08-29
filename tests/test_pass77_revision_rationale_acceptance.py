from pathlib import Path
from fastapi.testclient import TestClient
from legal.drafting.revision_rationale import RevisionRationaleStore
from legal.documents.workspace import create_document
from maine_family_law_llm import api as api_module
def _doc():return {'document_id':'f'*32,'current_revision_id':'e'*32,'content':'Fictional draft text.'}
def _payload():return {'reviewer_safe_id':'reviewer_001','change_summary':'Clarified fictional support statement.','reason':'Fictional reviewer identified an ambiguity.','affected_claim_ids':['claim_001'],'verifier_impact':'needs_recheck','user_confirmed':True}
def test_pass77_encrypted_rationale_is_revision_bound(tmp_path:Path):
 root=tmp_path/'matter';root.mkdir();s=RevisionRationaleStore(root,encryption_key='fictional-test-key');x=s.record(_payload(),document=_doc());assert x['revision_id']=='e'*32 and x['review_required'];assert 'Clarified fictional' not in s.path.read_text(encoding='utf-8')
def test_pass77_canonical_api_and_scope(monkeypatch,tmp_path:Path):
 a=tmp_path/'a';b=tmp_path/'b';a.mkdir();b.mkdir();active={'r':a};monkeypatch.setattr(api_module,'active_case_root',lambda:active['r']);monkeypatch.setenv('MAINE_MATTER_STORE_KEY','fictional-test-key');d=create_document(a,title='Fictional',content='Fictional draft text.',document_type='draft');c=TestClient(api_module.app);assert c.post(f"/api/drafting/documents/{d['document_id']}/revision-rationales",json=_payload()).status_code==200;assert c.get(f"/api/drafting/documents/{d['document_id']}/revision-rationales").json()['rationales'];active['r']=b;assert c.get(f"/api/drafting/documents/{d['document_id']}/revision-rationales").status_code==404
def test_pass77_mirrored_ui():
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();assert Path('src/maine_family_law_llm/ui/workbench.js').read_bytes()==Path('maine_family_law_llm/ui/workbench.js').read_bytes();assert 'Revision rationale ledger' in Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
