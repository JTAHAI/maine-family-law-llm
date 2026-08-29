from pathlib import Path
from legal.product.favorites import FavoritesStore

def test_pass118_encrypts_hash_bound_favorite_and_filters_local_role(tmp_path:Path):
 root=tmp_path/'m';root.mkdir();s=FavoritesStore(root,encryption_key='fictional-test-key')
 p=s.create({'favorite_id':'record_pin_001','kind':'record','label':'Fictional order','target':{'record_id':'record_001','source_hash':'a'*64},'visibility':'private','owner_role':'attorney','user_confirmed':True})
 assert p['favorite']['review_required'] is True and 'Fictional order' not in s.path.read_text(encoding='utf-8')
 assert len(s.list('attorney')['favorites'])==1 and s.list('paralegal')['favorites']==[]
 assert s.get('record_pin_001','attorney')['target']['record_id']=='record_001'

def test_pass118_shipped_api_ui_and_mirrors_are_present():
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes()
 api=Path('src/maine_family_law_llm/api.py').read_text(encoding='utf-8');ui=Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
 assert '"/api/favorites"' in api and 'Favorites and pins' in ui and 'local role filter' in ui
