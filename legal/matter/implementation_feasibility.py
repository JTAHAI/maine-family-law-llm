"""Encrypted, source-bound proposal feasibility flags; never determines validity, enforceability, or outcome."""
from __future__ import annotations
import hashlib,json,os,re,uuid
from copy import deepcopy
from datetime import UTC,datetime
from pathlib import Path
from typing import Any,Iterable
from legal.matter.intake_workbench import IntakeWorkbenchError
from legal.security.durable_io import atomic_write_bytes,exclusive_file_lock
from legal.security.local_encryption import LocalEnvelopeEncryptor
from legal.security.strict_json import strict_json_load_path
_ID=re.compile(r'[a-z][a-z0-9_-]{2,79}\Z');_HASH=re.compile(r'[a-f0-9]{64}\Z');_DATE=re.compile(r'\b(?:20\d\d[-/]\d\d[-/]\d\d|\d{1,2}/\d{1,2}/20\d\d)\b')
def _now():return datetime.now(UTC).replace(microsecond=0).isoformat().replace('+00:00','Z')
def _dig(v):return hashlib.sha256(json.dumps(v,sort_keys=True,separators=(',',':')).encode()).hexdigest()
def _id(v,n):
 x=str(v or '').strip().casefold()
 if not _ID.fullmatch(x):raise IntakeWorkbenchError(f'{n}_invalid')
 return x
def _txt(v,n,l=4000):
 x=' '.join(str(v or '').replace('\x00','').split())
 if not x:raise IntakeWorkbenchError(f'{n}_required')
 if len(x)>l:raise IntakeWorkbenchError(f'{n}_too_long')
 return x
class ImplementationFeasibilityStore:
 schema='maine_family_law_llm.implementation_feasibility.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(root).resolve();self.root=self.case_root/'35_NEGOTIATION'/'implementation-feasibility'
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError('implementation_feasibility_store_unavailable',409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'reviews.json.enc'
 @property
 def lock(self):return self.root/'.reviews.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'scope':self.scope,'rows':[],'ledger':[],'revision':0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=16*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('implementation_feasibility_store_unavailable',409) from e
  if v.get('schema')!=self.schema or v.get('scope')!=self.scope:raise IntakeWorkbenchError('cross_matter_access_denied',404)
  v.setdefault('rows',[]);v.setdefault('ledger',[]);v.setdefault('revision',0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _pub(v):
  o=deepcopy(v);o.update({'status':'review_required','review_required':True,'filing_ready':False,'local_only':True,'validity':'not_determined','enforceability':'not_determined','notice':'This flags textual operational ambiguities for reviewer follow-up. It does not determine contract validity, enforceability, legal effect, agreement, or outcome.'});return o
 def create(self,p,*,records:Iterable[dict]):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('implementation_feasibility_confirmation_required',409)
  raw=p.get('clauses')
  if not isinstance(raw,list) or not raw or len(raw)>80:raise IntakeWorkbenchError('implementation_feasibility_clauses_invalid')
  available={str(x.get('evidence_id') or x.get('source_id') or '').casefold():(str(x.get('evidence_id') or x.get('source_id') or ''),x) for x in records if isinstance(x,dict)};clauses=[];topics={};flags=[]
  for x in raw:
   if not isinstance(x,dict):raise IntakeWorkbenchError('implementation_feasibility_clause_invalid')
   cid=_id(x.get('clause_id'),'implementation_feasibility_clause_id');topic=_id(x.get('topic'),'implementation_feasibility_topic');text=_txt(x.get('text'),'implementation_feasibility_text');source=dict(x.get('source_ref') or {});rid=str(source.get('record_id') or '');h=str(source.get('source_hash') or '').casefold();found=available.get(rid.casefold())
   if not rid or not _HASH.fullmatch(h) or found is None or str(found[1].get('source_hash') or found[1].get('sha256') or '').casefold()!=h:raise IntakeWorkbenchError('implementation_feasibility_source_not_in_active_matter',404)
   if topic in topics and topics[topic]!=text:flags.append({'kind':'possible_internal_conflict','topic':topic,'clause_id':cid,'status':'review_required'})
   topics[topic]=text;lower=text.casefold()
   if any(token in lower for token in ('tbd','to be determined','as agreed','reasonable')):flags.append({'kind':'undefined_or_ambiguous_term','topic':topic,'clause_id':cid,'status':'review_required'})
   if topic in {'schedule','implementation','exchange'} and not _DATE.search(text):flags.append({'kind':'date_or_timing_missing','topic':topic,'clause_id':cid,'status':'review_required'})
   clauses.append({'clause_id':cid,'topic':topic,'text':text,'source_ref':{'record_id':found[0],'source_hash':h,'page':source.get('page')},'review_required':True})
  row={'review_id':_id(p.get('review_id'),'implementation_feasibility_review_id'),'reviewer_safe_id':_id(p.get('reviewer_safe_id'),'reviewer_safe_id'),'clauses':clauses,'flags':flags,'created_at':_now(),'review_required':True,'filing_ready':False};row['review_hash']=_dig({k:v for k,v in row.items() if k!='created_at'})
  with exclusive_file_lock(self.lock):
   state=self._load()
   if any(x.get('review_id')==row['review_id'] for x in state['rows']):raise IntakeWorkbenchError('implementation_feasibility_review_id_exists',409)
   state['rows'].append(row);e={'event_id':f'implementation_{uuid.uuid4().hex}','at':_now(),'action':'implementation_feasibility_review_created','review_id':row['review_id'],'previous_event_hash':str(state['ledger'][-1].get('event_hash') or '') if state['ledger'] else '','review_required':True};e['event_hash']=_dig(e);state['ledger'].append(e);state['revision']+=1;self._save(state)
  return self._pub(row)
 def get(self,rid):
  row=next((x for x in self._load()['rows'] if x.get('review_id')==_id(rid,'implementation_feasibility_review_id')),None)
  if row is None:raise IntakeWorkbenchError('implementation_feasibility_review_not_found',404)
  return {'review':self._pub(row),'review_required':True,'local_only':True}
 def source(self,rid,cid):
  row=self.get(rid)['review'];clause=next((x for x in row['clauses'] if x.get('clause_id')==_id(cid,'implementation_feasibility_clause_id')),None)
  if clause is None:raise IntakeWorkbenchError('implementation_feasibility_clause_not_found',404)
  return {'review_id':row['review_id'],'clause_id':clause['clause_id'],'source':dict(clause['source_ref']),'review_required':True}
