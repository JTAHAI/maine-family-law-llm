"""Explicitly generated, encrypted daily matter-review digest."""
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
_ID=re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{1,119}\Z");_HASH=re.compile(r"[0-9a-f]{64}\Z")
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def _dig(v):return hashlib.sha256(_canon(v)).hexdigest()
def _id(v):
 x=str(v or '').strip()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError('daily_brief_id_invalid')
 return x
class DailyMatterBriefStore:
 schema='maine_family_law_llm.daily_matter_brief.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):self.root=Path(root).resolve()/'40_RUNTIME'/'daily-matter-brief';self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'briefs.json.enc'
 @property
 def lock(self):return self.root/'.briefs.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'briefs':{},'events':[],'revision':0}
  try:s=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=4*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('daily_brief_unavailable',409) from e
  if s.get('schema')!=self.schema:raise IntakeWorkbenchError('daily_brief_unavailable',409)
  return s
 def _write(self,s):atomic_write_bytes(self.path,_canon(self.encryptor.encrypt_json(s)),mode=0o600)
 def _event(self,s,brief_id,detail):
  e={'event_id':'brief_'+hashlib.sha256((brief_id+_now()).encode()).hexdigest()[:24],'at':_now(),'action':'daily_brief_generated','brief_id':brief_id,'detail':detail,'previous_event_hash':str(s['events'][-1].get('event_hash') or '') if s['events'] else '','review_required':True};e['event_hash']=_dig(e);s['events'].append(e);s['revision']=int(s.get('revision') or 0)+1;return e
 def _source(self,row):
  rid=str(row.get('evidence_id') or row.get('source_id') or '').strip();h=str(row.get('source_hash') or row.get('sha256') or '').casefold()
  return {'record_id':rid,'source_hash':h,'title':str(row.get('title') or row.get('safe_filename') or rid)[:300]} if _ID.fullmatch(rid) and _HASH.fullmatch(h) else None
 def build(self,p,records):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('daily_brief_confirmation_required',409)
  bid=_id(p.get('brief_id'));changed=[];reviews=[];deadlines=[];blockers=[]
  for row in records:
   src=self._source(row)
   if not src:continue
   text=json.dumps(row,default=str).casefold();state=str(row.get('review_state') or row.get('parser_status') or '').casefold()
   if any(k in text for k in ('modified','changed','updated')):changed.append(src)
   if 'review' in state or 'review_required' in text:reviews.append(src)
   if any(k in text for k in ('deadline','hearing','due_date')):deadlines.append(src)
   if any(k in text for k in ('blocker','missing','unreadable','unsupported')):blockers.append(src)
  brief={'brief_id':bid,'generated_at':_now(),'changed_records':changed[:100],'due_reviews':reviews[:100],'deadline_candidates':deadlines[:100],'blockers':blockers[:100],'review_required':True,'notice':'This explicit local digest groups current metadata for review. It does not determine what changed, a deadline, completeness, a blocker, or legal effect.'}
  with exclusive_file_lock(self.lock):
   s=self._load();s['briefs'][bid]=brief;e=self._event(s,bid,{'changed':len(changed),'reviews':len(reviews),'deadlines':len(deadlines),'blockers':len(blockers)});self._write(s)
  return {'brief':deepcopy(brief),'receipt':deepcopy(e),'local_only':True,'network_used':False}
 def get(self,bid):
  x=self._load()['briefs'].get(_id(bid))
  if not x:raise IntakeWorkbenchError('daily_brief_not_found',404)
  return {'brief':deepcopy(x),'review_required':True,'local_only':True,'network_used':False}
