from pathlib import Path
from fastapi.testclient import TestClient
from legal.runtime.low_memory_mode import LowMemoryModeStore
from maine_family_law_llm import api as api_module

def test_pass109_low_memory_posture_is_encrypted_reversible_and_explicit(tmp_path:Path):
 root=tmp_path/'fictional-matter';root.mkdir();store=LowMemoryModeStore(root,encryption_key='fictional-test-key')
 active=store.set_active({'active':True,'user_confirmed':True})
 assert active['active'] is True and active['fallbacks']['retrieval']=='lexical_only' and active['fallbacks']['max_batch_items']==1
 assert 'low_memory_mode_activated'==active['receipt']['action'] and 'low_memory_mode_activated' not in store.path.read_text(encoding='utf-8')
 normal=store.set_active({'active':False,'user_confirmed':True});assert normal['active'] is False

def test_pass109_api_scope_and_shipped_ui(monkeypatch,tmp_path:Path):
 a,b=tmp_path/'a',tmp_path/'b';a.mkdir();b.mkdir();active={'root':a};monkeypatch.setattr(api_module,'active_case_root',lambda:active['root']);monkeypatch.setenv('MAINE_MATTER_STORE_KEY','fictional-test-key');c=TestClient(api_module.app)
 assert c.put('/api/runtime/low-memory-mode',json={'active':True,'user_confirmed':True}).status_code==200
 active['root']=b;assert c.get('/api/runtime/low-memory-mode').json()['active'] is False
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();assert 'Low-memory mode' in Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
