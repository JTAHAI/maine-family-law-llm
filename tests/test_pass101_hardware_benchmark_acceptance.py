from pathlib import Path
from fastapi.testclient import TestClient
from legal.runtime.hardware_benchmark import HardwareBenchmarkStore
from maine_family_law_llm import api as api_module
def test_pass101_local_encrypted_measurement_no_model_claim(tmp_path:Path):
 root=tmp_path/'m';root.mkdir();s=HardwareBenchmarkStore(root,encryption_key='fictional-test-key');r=s.run({'benchmark_id':'hardware_001','user_confirmed':True});assert r['network_used'] is False and r['model_throughput']['status']=='not_measured';assert 'hardware_001' not in s.path.read_text()
def test_pass101_api_scope_mirrors_and_ui(monkeypatch,tmp_path:Path):
 a,b=tmp_path/'a',tmp_path/'b';a.mkdir();b.mkdir();active={'root':a};monkeypatch.setattr(api_module,'active_case_root',lambda:active['root']);monkeypatch.setenv('MAINE_MATTER_STORE_KEY','fictional-test-key');c=TestClient(api_module.app);assert c.post('/api/runtime/hardware-benchmarks',json={'benchmark_id':'hardware_001','user_confirmed':True}).status_code==200;active['root']=b;assert c.get('/api/runtime/hardware-benchmarks/hardware_001').status_code==404;assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();assert 'Hardware benchmark' in Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
