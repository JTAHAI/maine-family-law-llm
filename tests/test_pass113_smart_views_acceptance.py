from pathlib import Path
from legal.product.smart_views import SmartViewStore

def test_pass113_encrypts_scoped_view_and_filters_fictional_review_queue(tmp_path:Path):
 root=tmp_path/'m';root.mkdir();s=SmartViewStore(root,encryption_key='fictional-test-key');created=s.create({'view_id':'review_001','kind':'review_queue','title':'Review queue','user_confirmed':True});assert created['view']['review_required'] is True
 result=s.run('review_001',[{'evidence_id':'record_001','title':'Fictional order','review_state':'review_required'}]);assert result['result_count']==1 and result['network_used'] is False
 assert 'review_001' not in s.path.read_text(encoding='utf-8')

def test_pass113_shipped_routes_and_ui_are_mirrored():
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes();ui=Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8');assert '/api/smart-views' in ui and 'Saved smart views' in ui
