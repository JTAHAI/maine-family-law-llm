from pathlib import Path
import pytest
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.product.user_labels import UserLabelsStore

def test_pass119_encrypts_collision_safe_labels_assignments_and_export_migration(tmp_path:Path):
 root=tmp_path/'m';root.mkdir();s=UserLabelsStore(root,encryption_key='fictional-test-key')
 s.create({'label_id':'priority_review','name':'Priority Review','color':'#1f7a8c','user_confirmed':True})
 with pytest.raises(IntakeWorkbenchError):s.create({'label_id':'priority_again','name':' priority review ','color':'#1f7a8c','user_confirmed':True})
 s.assign('priority_review',{'record_id':'record_001','source_hash':'a'*64,'user_confirmed':True})
 assert 'Priority Review' not in s.path.read_text(encoding='utf-8')
 exported=s.export({'user_confirmed':True})['export'];assert exported['sha256']
 other=UserLabelsStore(tmp_path/'other',encryption_key='fictional-test-key');out=other.import_export({'export':exported,'collision_strategy':'rename','user_confirmed':True});assert out['imported_label_ids']

def test_pass119_shipped_api_ui_and_mirror_are_present():
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes()
 api=Path('src/maine_family_law_llm/api.py').read_text(encoding='utf-8');ui=Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
 assert '"/api/user-labels"' in api and 'User-defined labels' in ui and 'collision_strategy' in ui
