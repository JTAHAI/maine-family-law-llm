"""Encrypted active-matter smart-view filters with review-only results."""
from __future__ import annotations
import hashlib,json,os,re
from copy import deepcopy
from datetime import UTC,datetime
from pathlib import Path
from typing import Any
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes,exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path
_ID=re.compile(r'[a-z][a-z0-9_-]{2,79}\Z');_KINDS=frozenset({'deadlines','blockers','missing_proof','unread_records','review_queue'})
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _dig(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _id(v):
 x=str(v or '').strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError('smart_view_id_invalid')
 return x
class SmartViewStore:
 schema='maine_family_law_llm.smart_views.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):self.root=Path(root).resolve()/'40_RUNTIME'/'smart-views';self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'views.json.enc'
 @property
 def lock(self):return self.root/'.views.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'views':{},'events':[],'revision':0}
  try:s=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=2*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('smart_views_unavailable',409) from e
  if s.get('schema')!=self.schema:raise IntakeWorkbenchError('smart_views_unavailable',409)
  return s
 def _write(self,s):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(s),sort_keys=True).encode(),mode=0o600)
 def create(self,p:dict[str,Any]):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('smart_view_confirmation_required',409)
  vid=_id(p.get('view_id'));kind=str(p.get('kind') or '').strip().casefold();title=' '.join(str(p.get('title') or kind).split())[:120]
  if kind not in _KINDS or not title:raise IntakeWorkbenchError('smart_view_kind_invalid')
  with exclusive_file_lock(self.lock):
   s=self._load()
   if vid in s['views']:raise IntakeWorkbenchError('smart_view_id_exists',409)
   row={'view_id':vid,'kind':kind,'title':title,'created_at':_now(),'review_required':True,'local_only':True,'network_used':False};s['views'][vid]=row;e={'event_id':'view_'+hashlib.sha256((vid+_now()).encode()).hexdigest()[:20],'at':_now(),'action':'smart_view_created','view_id':vid,'previous_event_hash':str(s['events'][-1].get('event_hash') or '') if s['events'] else '','review_required':True};e['event_hash']=_dig(e);s['events'].append(e);s['revision']=int(s.get('revision') or 0)+1;self._write(s)
  return {'view':deepcopy(row),'receipt':deepcopy(e)}
 def list(self):return {'views':[deepcopy(x) for x in self._load()['views'].values()],'review_required':True,'network_used':False}
 def run(self,view_id:str,records:list[dict[str,Any]]):
  row=self._load()['views'].get(_id(view_id))
  if not row:raise IntakeWorkbenchError('smart_view_not_found',404)
  kind=row['kind'];out=[]
  for r in records:
   rid=str(r.get('evidence_id') or r.get('source_id') or '').strip();status=str(r.get('review_state') or r.get('parser_status') or '').casefold();text=json.dumps(r,default=str).casefold()
   match=(kind=='deadlines' and any(k in text for k in ('deadline','hearing','due_date'))) or (kind=='blockers' and 'block' in text) or (kind=='missing_proof' and any(k in text for k in ('missing_proof','missing record','gap'))) or (kind=='unread_records' and status in {'unreadable','unsupported','metadata_only'}) or (kind=='review_queue' and ('review' in status or 'review_required' in text))
   if match and rid:out.append({'record_id':rid,'title':str(r.get('title') or r.get('safe_filename') or rid)[:300],'review_state':status or 'review_required'})
  return {'view':deepcopy(row),'status':'pass' if out else 'no_matches_review_required','results':out[:200],'result_count':len(out[:200]),'review_required':True,'network_used':False,'notice':'A smart view is a local review filter, not a finding, deadline calculation, or legal conclusion.'}
