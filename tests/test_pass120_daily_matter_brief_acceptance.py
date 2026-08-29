from pathlib import Path
from legal.product.daily_matter_brief import DailyMatterBriefStore

def test_pass120_builds_encrypted_explicit_local_review_digest(tmp_path:Path):
 root=tmp_path/'m';root.mkdir();s=DailyMatterBriefStore(root,encryption_key='fictional-test-key')
 row={'evidence_id':'record_001','source_hash':'a'*64,'title':'Fictional order','review_state':'review_required','annotations':'missing attachment deadline'}
 p=s.build({'brief_id':'daily_001','user_confirmed':True},[row]);assert len(p['brief']['due_reviews'])==1 and len(p['brief']['deadline_candidates'])==1
 assert 'Fictional order' not in s.path.read_text(encoding='utf-8') and s.get('daily_001')['brief']['brief_id']=='daily_001'

def test_pass120_shipped_api_ui_and_mirror_present():
 assert Path('src/maine_family_law_llm/api.py').read_bytes()==Path('maine_family_law_llm/api.py').read_bytes()
 api=Path('src/maine_family_law_llm/api.py').read_text(encoding='utf-8');ui=Path('src/maine_family_law_llm/ui/workbench.js').read_text(encoding='utf-8')
 assert '"/api/daily-matter-briefs"' in api and 'Daily matter brief' in ui
