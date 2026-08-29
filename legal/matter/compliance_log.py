"""Encrypted source-bound observations against exact order terms; never determines compliance, violation, contempt, or findings."""
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
_ID=re.compile(r'[a-z][a-z0-9_-]{2,79}\Z');_HASH=re.compile(r'[a-f0-9]{64}\Z');_STATES={'allegation','observation','finding_not_available'}
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
class ComplianceLogStore:
 schema='maine_family_law_llm.compliance_log.v1'
 def __init__(self,root:str|Path,*,encryption_key:str|None=None):
  self.case_root=Path(root).resolve();self.root=self.case_root/'21_ORDER_INTELLIGENCE'/'compliance-log'
  if not self.case_root.is_dir() or self.case_root.is_symlink() or (self.root.exists() and self.root.is_symlink()):raise IntakeWorkbenchError('compliance_log_store_unavailable',409)
  self.scope=hashlib.sha256(str(self.case_root).encode()).hexdigest()[:24];self.encryptor=LocalEnvelopeEncryptor(encryption_key or os.environ.get('MAINE_MATTER_STORE_KEY') or 'local-development-key-change-me')
 @property
 def path(self):return self.root/'events.json.enc'
 @property
 def lock(self):return self.root/'.events.lock'
 def _load(self):
  if not self.path.exists():return {'schema':self.schema,'scope':self.scope,'rows':[],'ledger':[],'revision':0}
  try:v=self.encryptor.decrypt_json(strict_json_load_path(self.path,max_bytes=16*1024*1024,require_object=True))
  except Exception as e:raise IntakeWorkbenchError('compliance_log_store_unavailable',409) from e
  if v.get('schema')!=self.schema or v.get('scope')!=self.scope:raise IntakeWorkbenchError('cross_matter_access_denied',404)
  v.setdefault('rows',[]);v.setdefault('ledger',[]);v.setdefault('revision',0);return v
 def _save(self,v):atomic_write_bytes(self.path,json.dumps(self.encryptor.encrypt_json(v),sort_keys=True).encode(),mode=0o600)
 @staticmethod
 def _pub(v):
  o=deepcopy(v);o.update({'status':'review_required','review_required':True,'filing_ready':False,'local_only':True,'compliance':'not_determined','violation':'not_determined','contempt':'not_determined','notice':'This log preserves source-bound allegations and observations against exact reviewer-selected order language. It does not determine compliance, violation, contempt, credibility, or a finding.'});return o
 def create(self,p,*,terms:Iterable[dict],records:Iterable[dict]):
  if p.get('user_confirmed') is not True:raise IntakeWorkbenchError('compliance_log_confirmation_required',409)
  tid=_id(p.get('term_id'),'compliance_log_term_id');term=next((dict(x) for x in terms if isinstance(x,dict) and str(x.get('term_id') or '')==tid),None)
  if term is None:raise IntakeWorkbenchError('compliance_log_term_not_found',404)
  tr=dict(term.get('source_ref') or {});term_hash=str(tr.get('source_hash') or '').casefold();term_rid=str(tr.get('record_id') or '')
  available={str(x.get('evidence_id') or x.get('source_id') or '').casefold():(str(x.get('evidence_id') or x.get('source_id') or ''),x) for x in records if isinstance(x,dict)}
  order=available.get(term_rid.casefold())
  if not term_rid or not _HASH.fullmatch(term_hash) or order is None or str(order[1].get('source_hash') or order[1].get('sha256') or '').casefold()!=term_hash:raise IntakeWorkbenchError('compliance_log_term_source_not_in_active_matter',404)
  source=dict(p.get('event_source_ref') or {});rid=str(source.get('record_id') or '');h=str(source.get('source_hash') or '').casefold();event=available.get(rid.casefold())
  if not rid or not _HASH.fullmatch(h) or event is None or str(event[1].get('source_hash') or event[1].get('sha256') or '').casefold()!=h:raise IntakeWorkbenchError('compliance_log_event_source_not_in_active_matter',404)
  state=str(p.get('event_state') or 'observation')
  if state not in _STATES:raise IntakeWorkbenchError('compliance_log_event_state_invalid')
  row={'log_id':_id(p.get('log_id'),'compliance_log_id'),'reviewer_safe_id':_id(p.get('reviewer_safe_id'),'reviewer_safe_id'),'term':{'term_id':tid,'exact_language':_txt(term.get('exact_language'),'compliance_log_exact_term',20000),'source_ref':{'record_id':order[0],'source_hash':term_hash,'page':tr.get('page')}},'event':{'event_id':_id(p.get('event_id'),'compliance_log_event_id'),'date_candidate':_txt(p.get('date_candidate'),'compliance_log_date',64),'text':_txt(p.get('text'),'compliance_log_text'),'state':state,'source_ref':{'record_id':event[0],'source_hash':h,'page':source.get('page')}},'created_at':_now(),'review_required':True,'filing_ready':False};row['log_hash']=_dig({k:v for k,v in row.items() if k!='created_at'})
  with exclusive_file_lock(self.lock):
   state_doc=self._load()
   if any(x.get('log_id')==row['log_id'] for x in state_doc['rows']):raise IntakeWorkbenchError('compliance_log_id_exists',409)
   state_doc['rows'].append(row);e={'event_id':f'compliance_{uuid.uuid4().hex}','at':_now(),'action':'compliance_log_created','log_id':row['log_id'],'previous_event_hash':str(state_doc['ledger'][-1].get('event_hash') or '') if state_doc['ledger'] else '','review_required':True};e['event_hash']=_dig(e);state_doc['ledger'].append(e);state_doc['revision']+=1;self._save(state_doc)
  return self._pub(row)
 def get(self,lid):
  row=next((x for x in self._load()['rows'] if x.get('log_id')==_id(lid,'compliance_log_id')),None)
  if row is None:raise IntakeWorkbenchError('compliance_log_not_found',404)
  return {'log':self._pub(row),'review_required':True,'local_only':True}
 def source(self,lid):
  row=self.get(lid)['log']
  return {'log_id':row['log_id'],'source':dict(row['event']['source_ref']),'review_required':True,'filing_ready':False}
