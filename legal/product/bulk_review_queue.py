"""Encrypted, source-bound bulk review queue for an active matter."""
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
_KINDS=frozenset({'record','claim','citation','privacy_finding','correction'});_STATES=frozenset({'new','needs_review','qualified','resolved_with_review','deferred'})
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _canon(v):return json.dumps(v,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
def _dig(v):return hashlib.sha256(_canon(v)).hexdigest()
def _id(v,label):
 x=str(v or '').strip()
 if not _ID.fullmatch(x) or '..' in x or '/' in x or '\\' in x:raise IntakeWorkbenchError(f'bulk_review_{label}_invalid')
 return x
def _hash(v):
 x=str(v or '').strip().casefold()
 if not _HASH.fullmatch(x):raise IntakeWorkbenchError('bulk_review_source_hash_invalid')
 return x
class BulkReviewQueueStore:
 schema='maine_family_law_llm.bulk_review_queue.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):self.root=Path(root).resolve()/'40_RUNTIME'/'bulk-review-queue';self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'queue.json.enc'
 @property
 def lock(self):return self.root/'.queue.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'items':{},'events':[],'revision':0}
  try:s=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=2*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('bulk_review_unavailable',409) from e
  if s.get('schema')!=self.schema:raise IntakeWorkbenchError('bulk_review_unavailable',409)
  prior=''
  for event in s.get('events',[]):
   copy=dict(event);digest=str(copy.pop('event_hash',''))
   if copy.get('previous_event_hash')!=prior or digest!=_dig(copy):raise IntakeWorkbenchError('bulk_review_history_invalid',409)
   prior=digest
  return s
 def _write(self,s):atomic_write_bytes(self.path,_canon(self.encryptor.encrypt_json(s)),mode=0o600)
 def _event(self,s,action,item_id,detail):
  rows=s.setdefault('events',[]);event={'event_id':'bulk_'+hashlib.sha256((action+item_id+_now()).encode()).hexdigest()[:24],'at':_now(),'action':action,'item_id':item_id,'detail':deepcopy(detail),'previous_event_hash':str(rows[-1].get('event_hash') or '') if rows else '','review_required':True};event['event_hash']=_dig(event);rows.append(event);s['revision']=int(s.get('revision') or 0)+1;return event
 def _source(self,p):
  x=p.get('source_ref')
  if not isinstance(x,dict):raise IntakeWorkbenchError('bulk_review_source_required')
  return {'record_id':_id(x.get('record_id'),'record_id'),'source_hash':_hash(x.get('source_hash')),'page':max(0,min(int(x.get('page') or 0),100000))}
 def _public(self,row):return {k:deepcopy(row.get(k)) for k in ('item_id','kind','label','source_ref','state','reviewer_safe_id','created_at','updated_at','review_required','notice')}
 def create(self,p):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('bulk_review_confirmation_required',409)
  item_id=_id(p.get('item_id'),'id');kind=str(p.get('kind') or '').strip().casefold();label=' '.join(str(p.get('label') or '').split())[:300]
  if kind not in _KINDS or not label or '/' in label or '\\' in label:raise IntakeWorkbenchError('bulk_review_item_invalid')
  row={'item_id':item_id,'kind':kind,'label':label,'source_ref':self._source(p),'state':'new','reviewer_safe_id':'','created_at':_now(),'updated_at':_now(),'review_required':True,'notice':'Triage organizes a source-bound review item. It does not decide a fact, credibility, privacy outcome, legal effect, or filing readiness.'}
  with exclusive_file_lock(self.lock):
   s=self._load()
   if item_id in s['items']:raise IntakeWorkbenchError('bulk_review_id_exists',409)
   s['items'][item_id]=row;e=self._event(s,'bulk_item_created',item_id,{'kind':kind});self._write(s)
  return {'item':self._public(row),'receipt':deepcopy(e),'local_only':True,'network_used':False}
 def list(self):
  rows=sorted(self._load()['items'].values(),key=lambda x:str(x.get('updated_at') or ''),reverse=True)
  return {'items':[self._public(x) for x in rows],'review_required':True,'local_only':True,'network_used':False}
 def triage(self,item_id,p):
  state=str(p.get('state') or '').strip().casefold();reviewer=_id(p.get('reviewer_safe_id'),'reviewer_id')
  if state not in _STATES or p.get('user_confirmed') is not True:raise IntakeWorkbenchError('bulk_review_triage_invalid',409)
  with exclusive_file_lock(self.lock):
   s=self._load();row=s['items'].get(_id(item_id,'id'))
   if not row:raise IntakeWorkbenchError('bulk_review_not_found',404)
   row.update({'state':state,'reviewer_safe_id':reviewer,'updated_at':_now()});e=self._event(s,'bulk_item_triaged',row['item_id'],{'state':state,'reviewer_safe_id':reviewer});self._write(s)
  return {'item':self._public(row),'receipt':deepcopy(e),'local_only':True,'network_used':False}
 def source(self,item_id):
  row=self._load()['items'].get(_id(item_id,'id'))
  if not row:raise IntakeWorkbenchError('bulk_review_not_found',404)
  return {'source':deepcopy(row['source_ref']),'review_required':True,'local_only':True,'network_used':False}
