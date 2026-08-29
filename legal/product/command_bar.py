"""Permission-labelled universal command-bar search with no path disclosure."""
from __future__ import annotations
import re
from typing import Any

_SAFE_QUERY=re.compile(r"[^\w\s:.-]+",re.UNICODE)
def _text(v:Any,limit:int=300)->str:return ' '.join(str(v or '').replace('\x00',' ').split())[:limit]
def search(query:str,*,matter:dict[str,Any]|None=None,records:list[dict[str,Any]]|None=None,sources:list[dict[str,Any]]|None=None,drafts:list[dict[str,Any]]|None=None,limit:int=30)->dict[str,Any]:
 q=_SAFE_QUERY.sub(' ',_text(query,160)).casefold().strip()
 if len(q)<2:return {'results':[],'status':'query_refinement_required','review_required':True,'network_used':False}
 rows=[]
 def add(kind,id,label,hint,permission,target):
  hay=f'{kind} {label} {hint}'.casefold()
  if q in hay: rows.append({'result_id':f'{kind}:{id}','kind':kind,'label':_text(label),'hint':_text(hint),'permission_required':permission,'target':target,'review_required':True})
 add('command','open_matter','Open active matter','Open the active local matter setup','active_matter_read',{'action':'open_matter'})
 add('settings','privacy','Open privacy settings','Review local-only storage and export boundaries','settings_read',{'action':'open_privacy'})
 if matter:add('matter',str(matter.get('case_id') or 'active'),'Active matter',str(matter.get('label') or 'Local matter'),'active_matter_read',{'action':'open_matter'})
 for r in records or []:
  rid=_text(r.get('evidence_id') or r.get('source_id') or r.get('record_id'),160)
  if rid:add('record',rid,_text(r.get('title') or r.get('safe_filename') or rid),rid,'active_matter_read',{'action':'open_record','record_id':rid,'source_token':_text(r.get('source_token'),80)})
 for s in sources or []:
  sid=_text(s.get('source_id') or s.get('citation'),160)
  if sid:add('source',sid,_text(s.get('title') or s.get('citation') or sid),_text(s.get('citation') or s.get('freshness_status')), 'authority_read',{'action':'open_source','source_id':sid})
 for d in drafts or []:
  did=_text(d.get('outline_id') or d.get('draft_id'),160)
  if did:add('draft',did,_text(d.get('title') or did), 'Review-required drafting outline','active_matter_read',{'action':'open_draft','outline_id':did})
 return {'status':'pass' if rows else 'no_matches_review_required','results':rows[:max(1,min(int(limit),50))],'active_matter_only':True,'network_used':False,'review_required':True}
