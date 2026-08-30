from pathlib import Path
from fastapi.testclient import TestClient
from maine_family_law_llm import api as api_module

def test_watch_scan_is_active_matter_bound_and_metadata_only(monkeypatch,tmp_path:Path):
 case=tmp_path/'fictional';case.mkdir(); folder=tmp_path/'drop';folder.mkdir();(folder/'fictional.pdf').write_bytes(b'x')
 monkeypatch.setattr(api_module,'active_case_root',lambda:case)
 out=TestClient(api_module.app).post('/api/evidence/watch-folder/scan',json={'folder':str(folder)}); assert out.status_code==200
 body=out.json(); assert body['count']==1 and str(folder) not in str(body) and 'does not watch' in body['notice']

def test_watch_api_is_mirrored():
 root=Path(__file__).resolve().parents[1];a=(root/'src/maine_family_law_llm/api.py').read_text(encoding='utf-8');b=(root/'maine_family_law_llm/api.py').read_text(encoding='utf-8');assert a==b and '/api/evidence/watch-folder/scan' in a

def test_watch_folder_ui_uses_resilient_delegated_handler():
 root=Path(__file__).resolve().parents[1]
 source=(root/'src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
 mirror=(root/'maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
 assert source==mirror
 assert "watchFolderDelegationBound" in source
 assert "closest('#watch-folder-scan')" in source
 assert "Scanning candidate metadata locally" in source
