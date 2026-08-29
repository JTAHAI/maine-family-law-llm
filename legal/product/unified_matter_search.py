"""Local-only active-matter search across safe record metadata and review state."""
from __future__ import annotations
import re
from typing import Any
def _clean(v:Any,n:int=400)->str:return ' '.join(str(v or '').replace('\x00',' ').split())[:n]
def search(query:str,records:list[dict[str,Any]],*,limit:int=100)->dict[str,Any]:
 q=' '.join(re.findall(r"[\w.-]+",str(query or '').casefold()))[:160]
 if len(q)<2:return {'status':'query_refinement_required','results':[],'review_required':True,'network_used':False}
 terms=q.split();out=[]
 fields=('title','safe_filename','document_date','date','citation','annotations','review_state','privacy_status','document_type','issue_labels','source_id','evidence_id')
 for row in records:
  values={key:_clean(row.get(key)) for key in fields}
  hay=' '.join(values.values()).casefold()
  if not all(term in hay for term in terms):continue
  matched=[key for key,value in values.items() if any(term in value.casefold() for term in terms)]
  rid=_clean(row.get('evidence_id') or row.get('source_id'),160)
  if rid:out.append({'record_id':rid,'title':values['title'] or values['safe_filename'] or rid,'matched_fields':matched,'date_candidate':values['document_date'] or values['date'],'citation':values['citation'],'review_state':values['review_state'] or 'review_required','privacy_status':values['privacy_status'] or 'unknown','review_required':True})
 return {'status':'pass' if out else 'no_matches_review_required','results':out[:max(1,min(int(limit),200))],'result_count':len(out[:max(1,min(int(limit),200))]),'matter_scope':'active_matter_only','network_used':False,'review_required':True,'notice':'Matches organize user-provided metadata and review state; they do not establish truth, legal effect, or filing readiness.'}
