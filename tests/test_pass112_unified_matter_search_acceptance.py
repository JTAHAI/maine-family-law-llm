from pathlib import Path
from fastapi.testclient import TestClient
from legal.product.unified_matter_search import search
from maine_family_law_llm import api as api_module

def test_pass112_searches_metadata_dates_citations_annotations_and_review_state():
 rows=[{'evidence_id':'record_001','title':'Fictional order','document_date':'2026-01-03','citation':'19-A M.R.S. § 1653','annotations':'parenting schedule','review_state':'needs review','privacy_status':'detected'}]
 result=search('1653',rows);assert result['status']=='pass' and result['results'][0]['matched_fields']==['citation']
 assert result['matter_scope']=='active_matter_only' and result['network_used'] is False

def test_pass112_api_requires_active_matter_and_ui_is_mirrored(monkeypatch,tmp_path:Path):
 root=tmp_path/'matter';root.mkdir();monkeypatch.setattr(api_module,'active_case_root',lambda:root);c=TestClient(api_module.app)
 assert c.get('/api/matter-search',params={'q':'order'}).status_code==200
 monkeypatch.setattr(api_module,'active_case_root',lambda:None);assert c.get('/api/matter-search',params={'q':'order'}).json()['status']=='blocked'
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();assert 'Unified matter search' in Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
