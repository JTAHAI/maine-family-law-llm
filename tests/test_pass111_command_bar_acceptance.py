from pathlib import Path
from fastapi.testclient import TestClient
from legal.product.command_bar import search
from maine_family_law_llm import api as api_module

def test_pass111_searches_scoped_commands_matter_records_sources_drafts_and_settings():
 result=search('order',matter={'case_id':'fictional_matter','label':'Fictional matter'},records=[{'evidence_id':'record_001','title':'Fictional order','source_token':'a'*64}],sources=[{'source_id':'source_001','title':'Maine order authority','citation':'19-A M.R.S. § 1653'}],drafts=[{'outline_id':'outline_001','title':'Order review outline'}])
 kinds={row['kind'] for row in result['results']}
 assert {'record','source','draft'} <= kinds
 assert all(row['permission_required'] in {'active_matter_read','authority_read','settings_read'} for row in result['results'])
 assert all('case_root' not in row for row in result['results']) and result['network_used'] is False

def test_pass111_api_is_active_matter_scoped_and_assets_are_mirrored(monkeypatch,tmp_path:Path):
 a,b=tmp_path/'a',tmp_path/'b';a.mkdir();b.mkdir();active={'root':a};monkeypatch.setattr(api_module,'active_case_root',lambda:active['root']);c=TestClient(api_module.app)
 response=c.get('/api/command-bar/search',params={'q':'privacy'});assert response.status_code==200
 assert response.json()['active_matter_only'] is True and all('case_root' not in row for row in response.json()['results'])
 active['root']=None;assert c.get('/api/command-bar/search',params={'q':'privacy'}).status_code==200
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();ui=Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8');assert '/api/command-bar/search' in ui and 'commandBarDefinitions' in ui
